"""In-memory fakes for Firebase Auth and the Firestore user store."""

from datetime import UTC, datetime
from typing import Any

from app.identity import IdentityUser, InvalidTokenError
from app.models import Role, UserProfile


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
