"""In-memory fakes for Firebase Auth, Firestore stores and the clock."""

import itertools
from datetime import UTC, datetime, timedelta
from typing import Any

from app.identity import IdentityUser, InvalidTokenError
from app.models import (
    Bag,
    BagStatus,
    Household,
    Pickup,
    PickupStatus,
    Role,
    RouteStop,
    UserProfile,
    WasteRecord,
)
from app.models import (
    CatalogItem,
    ConsentEntry,
    HouseholdStats,
    LedgerEntry,
    Partner,
    SwapsCache,
    TipsCache,
    WasteRecordStatus,
)


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
        self.routes: dict[str, RouteStop] = {}
        self.records: dict[str, WasteRecord] = {}
        self.stats: dict[str, HouseholdStats] = {}
        self.ledger: dict[str, dict[str, LedgerEntry]] = {}
        self.tips: dict[tuple[str, str], TipsCache] = {}
        self.consent: dict[str, list[ConsentEntry]] = {}
        self.partners: dict[str, Partner] = {}
        self.catalogs: dict[str, dict[str, CatalogItem]] = {}
        self.swaps: dict[str, SwapsCache] = {}
        self.events: dict[tuple[str, str, str, str], int] = {}
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

    def get_households(self, household_ids: list[str]) -> dict[str, Household]:
        return {h: self.households[h] for h in household_ids if h in self.households}

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

    def list_bags_by_status(self, status: BagStatus) -> list[Bag]:
        return [b for b in self.bags.values() if b.status == status]

    def get_waste_records(self, codes: list[str]) -> dict[str, WasteRecord]:
        return {c: self.records[c] for c in codes if c in self.records}

    def save_waste_record(self, record: WasteRecord) -> None:
        self.records[record.bagCode] = record

    def list_confirmed_records(self, household_id: str) -> list[WasteRecord]:
        return [r for r in self.records.values()
                if r.householdId == household_id and r.status == WasteRecordStatus.CONFIRMED]

    def get_pickups(self, pickup_ids: list[str]) -> dict[str, Pickup]:
        return {p: self.pickups[p] for p in pickup_ids if p in self.pickups}

    def get_stats(self, household_id: str) -> HouseholdStats | None:
        return self.stats.get(household_id)

    def get_tips(self, household_id: str, lang: str) -> TipsCache | None:
        return self.tips.get((household_id, lang))

    def save_tips(self, household_id: str, cache: TipsCache) -> None:
        self.tips[(household_id, cache.lang)] = cache

    def list_consent_history(self, household_id: str, limit: int = 10) -> list[ConsentEntry]:
        return sorted(self.consent.get(household_id, []), key=lambda e: e.at, reverse=True)[:limit]

    # --- partners & swaps ---
    def get_partner(self, partner_id: str) -> Partner | None:
        return self.partners.get(partner_id)

    def list_partners(self) -> list[Partner]:
        return list(self.partners.values())

    def list_catalog(self, partner_id: str) -> list[CatalogItem]:
        return list(self.catalogs.get(partner_id, {}).values())

    def save_partner(self, partner: Partner, catalog: list[CatalogItem]) -> None:
        self.partners[partner.id] = partner
        self.catalogs.setdefault(partner.id, {}).update({i.sku: i for i in catalog})

    def list_consenting_households(self) -> list[Household]:
        return [h for h in self.households.values() if h.consent.dataSharing]

    def get_stats_many(self, household_ids: list[str]) -> dict[str, HouseholdStats]:
        return {h: self.stats[h] for h in household_ids if h in self.stats}

    def get_swaps(self, household_id: str) -> SwapsCache | None:
        return self.swaps.get(household_id)

    def save_swaps(self, household_id: str, cache: SwapsCache) -> None:
        self.swaps[household_id] = cache

    def delete_swaps(self, household_id: str) -> None:
        self.swaps.pop(household_id, None)

    def count_swap_event(self, partner_id: str, day: str, sku: str, kind: str) -> None:
        key = (partner_id, day, kind, sku)
        self.events[key] = self.events.get(key, 0) + 1

    # --- admin ---
    def count_pickups(self, status: str, date_from: str, date_to: str, synthetic_only: bool = False) -> int:
        return sum(1 for p in self.pickups.values()
                   if p.status == status and date_from <= p.date <= date_to and (p.isSynthetic or not synthetic_only))

    def list_all_stats(self) -> list[tuple[str, HouseholdStats]]:
        return list(self.stats.items())

    def list_quality_records(self) -> list[WasteRecord]:
        return [r for r in self.records.values()
                if r.status == WasteRecordStatus.CONFIRMED and r.source in ("ai", "ai_edited", "manual")]

    def list_draft_records(self) -> list[WasteRecord]:
        return [r for r in self.records.values() if r.status == WasteRecordStatus.DRAFT]

    def list_pickups_by_date(self, day: str, zone: str | None = None, status: str | None = None) -> list[Pickup]:
        return [p for p in self.pickups.values()
                if p.date == day and (zone is None or p.zone == zone) and (status is None or p.status == status)]

    def list_partner_metrics(self, partner_id: str, since_day: str) -> list[dict]:
        days: dict[str, dict] = {}
        for (pid, day, kind, sku), n in self.events.items():
            if pid == partner_id and day >= since_day:
                days.setdefault(day, {"day": day}).setdefault(kind, {})[sku] = n
        return list(days.values())

    def get_pickup(self, pickup_id: str) -> Pickup | None:
        return self.pickups.get(pickup_id)

    def list_pickups(self, household_id: str) -> list[Pickup]:
        pickups = [p for p in self.pickups.values() if p.householdId == household_id]
        return sorted(pickups, key=lambda p: (p.date, p.createdAt), reverse=True)

    def list_requested_pickups(self, zones: list[str], day: str) -> list[Pickup]:
        return [
            p for p in self.pickups.values()
            if p.zone in zones and p.date == day and p.status == PickupStatus.REQUESTED
        ]

    def list_collector_pickups(
        self, collector_uid: str, *, day: str | None = None, status: PickupStatus | None = None
    ) -> list[Pickup]:
        return [
            p for p in self.pickups.values()
            if p.collectorUid == collector_uid
            and (day is None or p.date == day)
            and (status is None or p.status == status)
        ]

    def new_pickup_id(self) -> str:
        return f"pickup-{next(self._ids)}"

    def commit(
        self,
        pickups: list[Pickup],
        bags: list[Bag],
        routes: list[RouteStop] | None = None,
        records: list[WasteRecord] | None = None,
        *,
        households: list[Household] | None = None,
        stats: list[tuple[str, HouseholdStats]] | None = None,
        ledger: list[tuple[str, LedgerEntry]] | None = None,
        consent: list[tuple[str, ConsentEntry]] | None = None,
    ) -> None:
        self.commits += 1
        for household in households or []:
            self.households[household.id] = household
        for household_id, summary in stats or []:
            self.stats[household_id] = summary
        for household_id, entry in ledger or []:
            self.ledger.setdefault(household_id, {})[entry.id] = entry
        for household_id, entry in consent or []:
            self.consent.setdefault(household_id, []).append(entry)
        for pickup in pickups:
            self.pickups[pickup.id] = pickup
        for bag in bags:
            self.bags[bag.code] = bag
        for route in routes or []:
            self.routes[route.pickupId] = route
        for record in records or []:
            self.records[record.bagCode] = record


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

    def create_staff_user(self, email: str, display_name: str) -> tuple[str, str]:
        from app.errors import DomainError

        if email in self.taken_emails:
            raise DomainError(409, "email_exists")
        self.taken_emails.add(email)
        uid = f"staff-{len(self.users) + 1}"
        self.users[uid] = IdentityUser(uid, email, display_name, None)
        return uid, f"https://reset.example/{uid}"


class FakeUserStore:
    def __init__(self) -> None:
        self.docs: dict[str, UserProfile] = {}

    def get(self, uid: str) -> UserProfile | None:
        return self.docs.get(uid)

    def upsert(self, uid: str, name: str, email: str | None, role: Role) -> UserProfile:
        created = self.docs[uid].createdAt if uid in self.docs else datetime.now(UTC)
        zones = self.docs[uid].zones if uid in self.docs else []
        self.docs[uid] = UserProfile(
            uid=uid, name=name, email=email, role=role, createdAt=created, zones=zones
        )
        return self.docs[uid]

    def set_zones(self, uid: str, zones: list[str]) -> None:
        self.docs[uid] = self.docs[uid].model_copy(update={"zones": list(zones)})

    def list_by_role(self, role: Role) -> list[UserProfile]:
        return [p for p in self.docs.values() if p.role == role]

    def count_by_role(self, role: Role) -> int:
        return len(self.list_by_role(role))

    def save(self, profile: UserProfile) -> None:
        self.docs[profile.uid] = profile


# --- warehouse / AI fakes ---


class FakeClassifier:
    """Returns `result`, or raises `error` (an AiError) when set."""

    model = "fake-gemini"

    def __init__(self) -> None:
        from app.models import AiItem, AiResult

        self.calls: list[list[tuple[bytes, str]]] = []
        self.error: Exception | None = None
        self.result = AiResult(
            items=[
                AiItem(name="plastic bottle", category="plastic", material="PET", productType="drink bottle",
                       brand=None, quantity=3, recyclable=True, confidence=0.95),
                AiItem(name="aluminium can", category="metal", material="aluminium", productType="drink can",
                       brand="Lion", quantity=2, recyclable=True, confidence=0.9),
                AiItem(name="food wrapper", category="plastic", material="film", productType="wrapper",
                       brand=None, quantity=1, recyclable=False, confidence=0.4),
            ],
            segregationQuality="mixed",
            hazardFlags=[],
            notes="Mostly drink containers.",
        )

    def classify(self, images: list[tuple[bytes, str]]):  # noqa: ANN201
        from app.ai.classifier import Classification
        from app.models import TokenUsage

        self.calls.append(images)
        if self.error is not None:
            raise self.error
        return Classification(
            result=self.result, model=self.model, latency_ms=1234,
            token_usage=TokenUsage(prompt=1300, output=150, thoughts=0, total=1450), raw={},
        )


class FakePhotoStore:
    def __init__(self) -> None:
        self.saved: list[str] = []
        self.fail = False

    def save(self, bag_code: str, photos: list, now: datetime) -> list[str]:  # noqa: ANN001
        if self.fail:
            raise RuntimeError("storage down")
        paths = [f"gs://test-bucket/bags/{bag_code}/{len(self.saved) + i}.jpg" for i in range(len(photos))]
        self.saved.extend(paths)
        return paths


class FakeTipGenerator:
    """Counts calls; returns 3 tips in the requested language, or raises `error`."""

    model = "fake-gemini"

    def __init__(self) -> None:
        self.calls: list[tuple[dict, str]] = []
        self.error: Exception | None = None

    def generate(self, payload: dict, lang: str):  # noqa: ANN201
        from app.models import Tip

        self.calls.append((payload, lang))
        if self.error is not None:
            raise self.error
        tips = [Tip(title=f"{lang} tip {i}", body=f"Do thing {i}.", category="plastic") for i in range(1, 4)]
        return tips, 321


class FakeRanker:
    """Returns `response` as Gemini's raw ranking, or raises `error`."""

    model = "fake-gemini"

    def __init__(self) -> None:
        self.calls: list[dict] = []
        self.error: Exception | None = None
        self.response: dict | None = None  # None -> pick the first two candidates

    def rank(self, payload: dict):  # noqa: ANN201
        self.calls.append(payload)
        if self.error is not None:
            raise self.error
        if self.response is not None:
            return self.response, 111
        picks = [{"sku": c["sku"], "reason": f"Because of {c['sku']}."} for c in payload["candidates"][:2]]
        return {"picks": picks}, 111


class FakeDemoKeyReader:
    """Mimics SecretManagerDemoKeyReader: only the two demo partners have a readable key."""

    def read(self, partner_id: str) -> str:
        from app.errors import DomainError
        from app.secrets import DEMO_PARTNER_IDS

        if partner_id not in DEMO_PARTNER_IDS:
            raise DomainError(404, "not_a_demo_partner")
        return f"etp.{partner_id}.secret-from-secret-manager"
