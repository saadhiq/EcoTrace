"""Firebase Auth operations behind a small interface, so tests can fake them."""

from dataclasses import dataclass
from typing import Any, Protocol

from firebase_admin import auth

from app.firebase import firebase_app
from app.models import Role


class InvalidTokenError(Exception):
    """The ID token is missing, malformed, expired, revoked or not ours."""


@dataclass
class IdentityUser:
    uid: str
    email: str | None
    display_name: str | None
    role: Role | None
    disabled: bool = False


def parse_role(value: Any) -> Role | None:
    try:
        return Role(value)
    except ValueError:
        return None


class IdentityAdmin(Protocol):
    def verify_id_token(self, token: str) -> dict[str, Any]: ...

    def get_user(self, uid: str) -> IdentityUser | None: ...

    def create_user(self, uid: str, email: str, display_name: str) -> IdentityUser: ...

    def reset_user(self, uid: str, display_name: str) -> None: ...

    def set_role(self, uid: str, role: Role) -> None: ...

    def create_custom_token(self, uid: str) -> str: ...


class FirebaseIdentityAdmin:
    """IdentityAdmin backed by the Firebase Admin SDK."""

    def __init__(self) -> None:
        self._app = firebase_app()

    def verify_id_token(self, token: str) -> dict[str, Any]:
        try:
            return auth.verify_id_token(token, app=self._app)
        except (ValueError, auth.InvalidIdTokenError, auth.CertificateFetchError) as exc:
            # Expired/revoked token errors subclass InvalidIdTokenError.
            raise InvalidTokenError(str(exc)) from exc

    def get_user(self, uid: str) -> IdentityUser | None:
        try:
            record = auth.get_user(uid, app=self._app)
        except auth.UserNotFoundError:
            return None
        claims = record.custom_claims or {}
        return IdentityUser(
            uid=record.uid,
            email=record.email,
            display_name=record.display_name,
            role=parse_role(claims.get("role")),
            disabled=record.disabled,
        )

    def create_user(self, uid: str, email: str, display_name: str) -> IdentityUser:
        try:
            record = auth.create_user(
                uid=uid,
                email=email,
                email_verified=True,
                display_name=display_name,
                app=self._app,
            )
        except auth.EmailAlreadyExistsError:
            # Someone else holds the email; the demo account still works without it.
            record = auth.create_user(uid=uid, display_name=display_name, app=self._app)
        return IdentityUser(record.uid, record.email, record.display_name, role=None)

    def reset_user(self, uid: str, display_name: str) -> None:
        auth.update_user(uid, display_name=display_name, disabled=False, app=self._app)

    def set_role(self, uid: str, role: Role) -> None:
        # Replaces all custom claims, which also clears any tampered extras.
        auth.set_custom_user_claims(uid, {"role": role.value}, app=self._app)

    def create_custom_token(self, uid: str) -> str:
        token = auth.create_custom_token(uid, app=self._app)
        return token.decode() if isinstance(token, bytes) else token
