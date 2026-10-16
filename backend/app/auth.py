"""FastAPI dependencies: Firebase ID token verification and role checks."""

from collections.abc import Callable

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.identity import FirebaseIdentityAdmin, IdentityAdmin, InvalidTokenError, parse_role
from app.models import CurrentUser, Role
from app.users import FirestoreUserStore, UserStore

_bearer = HTTPBearer(auto_error=False)


def get_identity() -> IdentityAdmin:
    return FirebaseIdentityAdmin()


def get_user_store() -> UserStore:
    return FirestoreUserStore()


def _unauthorized(detail: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=detail,
        headers={"WWW-Authenticate": "Bearer"},
    )


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
    identity: IdentityAdmin = Depends(get_identity),
) -> CurrentUser:
    """Verify the `Authorization: Bearer <Firebase ID token>` header."""
    if credentials is None or not credentials.credentials:
        raise _unauthorized("missing_token")
    try:
        claims = identity.verify_id_token(credentials.credentials)
    except InvalidTokenError as exc:
        raise _unauthorized("invalid_token") from exc
    return CurrentUser(
        uid=claims["uid"],
        email=claims.get("email"),
        name=claims.get("name"),
        role=parse_role(claims.get("role")),
    )


def require_role(*roles: Role) -> Callable[..., CurrentUser]:
    """Dependency factory: allow only callers whose role claim is in `roles`."""

    def dependency(user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
        if user.role is None:
            raise HTTPException(status.HTTP_403_FORBIDDEN, detail="not_registered")
        if user.role not in roles:
            raise HTTPException(status.HTTP_403_FORBIDDEN, detail="forbidden")
        return user

    return dependency


require_registered = require_role(*Role)
