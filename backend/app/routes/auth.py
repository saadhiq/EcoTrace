"""Registration, profile and demo sign-in endpoints."""

import logging

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field

from app.auth import get_current_user, get_identity, get_user_store, require_registered
from app.clock import Clock
from app.demo import (
    ensure_demo_collector_data,
    ensure_demo_operator_data,
    ensure_demo_resident_data,
    ensure_demo_user,
    is_demo_uid,
)
from app.demo_history import ensure_demo_resident_history
from app.deps import get_clock, get_store
from app.identity import IdentityAdmin
from app.models import CurrentUser, Role, UserProfile
from app.ratelimit import RateLimiter, enforce
from app.store import DataStore
from app.users import UserStore

logger = logging.getLogger(__name__)
router = APIRouter()


class RegisterRequest(BaseModel):
    name: str | None = Field(default=None, max_length=80)


class RegisterResponse(BaseModel):
    profile: UserProfile
    # True when a new role claim was set: the client must refresh its ID token.
    refreshToken: bool


class DemoTokenResponse(BaseModel):
    token: str
    role: Role


def get_demo_limiter(request: Request) -> RateLimiter:
    return request.app.state.demo_limiter


def _display_name(requested: str | None, user: CurrentUser) -> str:
    for candidate in (requested, user.name):
        if candidate and candidate.strip():
            return candidate.strip()
    if user.email:
        return user.email.split("@", 1)[0]
    return "Resident"


@router.post("/auth/register", response_model=RegisterResponse)
def register(
    body: RegisterRequest | None = None,
    user: CurrentUser = Depends(get_current_user),
    identity: IdentityAdmin = Depends(get_identity),
    users: UserStore = Depends(get_user_store),
) -> RegisterResponse:
    """Self-signup always yields a resident. Existing roles are never changed."""
    requested_name = body.name if body else None
    # The server-side claim is authoritative; the caller's token may be stale.
    record = identity.get_user(user.uid)
    existing_role = (record.role if record else None) or user.role
    if existing_role is not None:
        profile = users.get(user.uid) or users.upsert(
            user.uid, _display_name(requested_name, user), user.email, existing_role
        )
        return RegisterResponse(profile=profile, refreshToken=user.role != existing_role)

    identity.set_role(user.uid, Role.RESIDENT)
    profile = users.upsert(
        user.uid, _display_name(requested_name, user), user.email, Role.RESIDENT
    )
    return RegisterResponse(profile=profile, refreshToken=True)


class MeResponse(UserProfile):
    # True for the shared demo accounts (enables demo-only helpers in the UI).
    isDemo: bool = False


@router.get("/me", response_model=MeResponse)
def me(
    user: CurrentUser = Depends(require_registered),
    users: UserStore = Depends(get_user_store),
) -> MeResponse:
    """Profile from Firestore; the role always comes from the verified token claim."""
    assert user.role is not None
    stored = users.get(user.uid)
    if stored is None:
        stored = UserProfile(
            uid=user.uid,
            name=user.name or (user.email or "").split("@", 1)[0] or "User",
            email=user.email,
            role=user.role,
        )
    return MeResponse(**stored.model_copy(update={"role": user.role}).model_dump(), isDemo=is_demo_uid(user.uid))


@router.post("/auth/demo/{role}", response_model=DemoTokenResponse)
def demo_sign_in(
    role: str,
    request: Request,
    limiter: RateLimiter = Depends(get_demo_limiter),
    identity: IdentityAdmin = Depends(get_identity),
    users: UserStore = Depends(get_user_store),
    store: DataStore = Depends(get_store),
    clock: Clock = Depends(get_clock),
) -> DemoTokenResponse:
    """Repair the demo user for `role` and return a Firebase custom token for it."""
    try:
        demo_role = Role(role)
    except ValueError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="invalid_role") from exc
    client = enforce(limiter, request)
    uid = ensure_demo_user(identity, users, demo_role)
    if demo_role == Role.RESIDENT:
        ensure_demo_resident_data(store, clock)
        ensure_demo_resident_history(store, clock)
    elif demo_role == Role.COLLECTOR:
        ensure_demo_collector_data(store, users, clock)
    elif demo_role == Role.OPERATOR:
        ensure_demo_operator_data(store, clock)
    logger.info("demo sign-in role=%s client=%s", demo_role.value, client)
    return DemoTokenResponse(token=identity.create_custom_token(uid), role=demo_role)
