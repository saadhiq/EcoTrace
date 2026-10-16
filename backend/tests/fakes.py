"""In-memory fakes for Firebase Auth, Firestore stores and the clock."""

import itertools
from datetime import UTC, datetime, timedelta
from typing import Any

from app.identity import IdentityUser, InvalidTokenError
from app.models import Bag, Household, Pickup, Role, UserProfile


class FixedClock:
    """Starts at 2026-03-10 09:00 Colombo time (03:30 UTC); advance() moves it."""

    def __init__(self, start: datetime | None = None) -> None:
        self.current = start or datetime(2026, 3, 10, 3, 30, tzinfo=UTC)

    def now(self) -> datetime:
        return self.current

    def advance(self, **kwargs: float) -> None:
        self.current += timedelta(**kwargs)


class FakeDataStore:
    def __init__(self) -> None:
        self.households: dict[str, Household] = {}
        self.bags: dict[str, Bag] = {}
        self.pickups: dict[str, Pickup] = {}
        self.commits = 0
        self._ids = itertools.count(1)
        # Codes create_bags() should treat as already taken (collision tests).
        self.reserved_codes: set[str] = set()

    def create_household(self, household: Household) -> bool:
        if household.id in self.households:
            return False
        self.households[household.id] = household
        return True

    def get_household(self, household_id: str) -> Household | None:
        return self.households.get(household_id)

    def save_household(self, household: Household) -> None:
        self.households[household.id] = household

    def create_bags(self, bags: list[Bag]) -> bool:
        if any(b.code in self.bags or b.code in self.reserved_codes for b in bags):
            return False
        for bag in bags:
            self.bags[bag.code] = bag
        return True

    def get_bags(self, codes: list[str]) -> dict[str, Bag]:
        return {code: self.bags[code] for code in codes if code in self.bags}

    def list_bags(self, household_id: str) -> list[Bag]:
        bags = [b for b in self.bags.values() if b.householdId == household_id]
        return sorted(bags, key=lambda b: (b.issuedAt, b.code))

    def get_pickup(self, pickup_id: str) -> Pickup | None:
        return self.pickups.get(pickup_id)

    def list_pickups(self, household_id: str) -> list[Pickup]:
        pickups = [p for p in self.pickups.values() if p.householdId == household_id]
        return sorted(pickups, key=lambda p: (p.date, p.createdAt), reverse=True)

    def new_pickup_id(self) -> str:
        return f"pickup-{next(self._ids)}"

    def commit(self, pickups: list[Pickup], bags: list[Bag]) -> None:
        self.commits += 1
        for pickup in pickups:
            self.pickups[pickup.id] = pickup
        for bag in bags:
            self.bags[bag.code] = bag


class FakeIdentity:
    def __init__(self) -> None:
        self.tokens: dict[str, dict[str, Any]] = {}
        self.users: dict[str, IdentityUser] = {}
        self.claims: dict[str, dict[str, Any]] = {}
        self.taken_emails: set[str] = set()

    # --- helpers for tests ---
    def issue(self, token: str, uid: str, **claims: Any) -> None:
        self.tokens[token] = {"uid": uid, **claims}

    def add_user(self, uid: str, role: Role | None = None, email: str | None = None) -> None:
        self.users[uid] = IdentityUser(uid, email, None, role)
        if role:
            self.claims[uid] = {"role": role.value}

    # --- IdentityAdmin ---
    def verify_id_token(self, token: str) -> dict[str, Any]:
        if token not in self.tokens:
            raise InvalidTokenError("unknown token")
        return self.tokens[token]

    def get_user(self, uid: str) -> IdentityUser | None:
        user = self.users.get(uid)
        if user is None:
            return None
        raw = self.claims.get(uid, {}).get("role")
        user.role = Role(raw) if raw in set(Role) else None
        return user

    def create_user(self, uid: str, email: str, display_name: str) -> IdentityUser:
        stored_email = None if email in self.taken_emails else email
        self.users[uid] = IdentityUser(uid, stored_email, display_name, None)
        return self.users[uid]

    def reset_user(self, uid: str, display_name: str) -> None:
        self.users[uid].display_name = display_name
        self.users[uid].disabled = False

    def set_role(self, uid: str, role: Role) -> None:
        self.claims[uid] = {"role": role.value}

    def create_custom_token(self, uid: str) -> str:
        return f"custom-token-for-{uid}"


class FakeUserStore:
    def __init__(self) -> None:
        self.docs: dict[str, UserProfile] = {}

    def get(self, uid: str) -> UserProfile | None:
        return self.docs.get(uid)

    def upsert(self, uid: str, name: str, email: str | None, role: Role) -> UserProfile:
        created = self.docs[uid].createdAt if uid in self.docs else datetime.now(UTC)
        self.docs[uid] = UserProfile(
            uid=uid, name=name, email=email, role=role, createdAt=created
        )
        return self.docs[uid]
