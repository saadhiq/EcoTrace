"""Admin endpoints. The demo admin can VIEW everything; account/partner/key changes are blocked."""

from datetime import date
from functools import lru_cache
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel, Field
from starlette.concurrency import run_in_threadpool

from app import admin
from app.auth import get_identity, get_user_store, require_role
from app.clock import Clock, local_today
from app.demo import is_demo_uid
from app.deps import get_clock, get_store
from app.identity import IdentityAdmin
from app.models import CurrentUser, Role, UserProfile
from app.secrets import DemoKeyReader, SecretManagerDemoKeyReader
from app.store import DataStore
from app.users import UserStore

router = APIRouter(prefix="/admin")
admin_only = require_role(Role.ADMIN)
DEMO_DISABLED = "demo_disabled"  # UI: "Disabled in the public demo"


def deny_in_demo(user: CurrentUser = Depends(admin_only)) -> CurrentUser:
    """THE demo guard: the public demo admin may not create/delete/change accounts, partners or keys."""
    if is_demo_uid(user.uid):
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail=DEMO_DISABLED)
    return user


def get_admin_cache(request: Request) -> admin.TTLCache:
    return request.app.state.admin_cache


@lru_cache
def _demo_key_reader() -> SecretManagerDemoKeyReader:
    return SecretManagerDemoKeyReader()


def get_demo_key_reader() -> DemoKeyReader:
    return _demo_key_reader()


# --- read endpoints (cached 60 s) ---


@router.get("/overview", response_model=admin.Overview)
def overview(
    range_: Literal["7d", "30d"] = Query(default="7d", alias="range"),
    synthetic: Literal["include", "exclude"] = Query(default="include"),
    _: CurrentUser = Depends(admin_only),
    store: DataStore = Depends(get_store),
    users: UserStore = Depends(get_user_store),
    clock: Clock = Depends(get_clock),
    cache: admin.TTLCache = Depends(get_admin_cache),
) -> admin.Overview:
    days = 7 if range_ == "7d" else 30
    return cache.get_or_set(
        ("overview", days, synthetic),
        lambda: admin.overview(store, users, clock, days, include_synthetic=synthetic == "include"),
    )


@router.get("/ai-quality", response_model=admin.AiQuality)
def ai_quality(
    _: CurrentUser = Depends(admin_only),
    store: DataStore = Depends(get_store),
    cache: admin.TTLCache = Depends(get_admin_cache),
) -> admin.AiQuality:
    return cache.get_or_set(
        ("ai-quality",), lambda: admin.ai_quality(store.list_quality_records(), store.list_draft_records())
    )


@router.get("/pickups", response_model=admin.PickupPage)
def pickups(
    day: date | None = Query(default=None, alias="date"),
    zone: str | None = None,
    status_: str | None = Query(default=None, alias="status"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=50, alias="pageSize"),
    _: CurrentUser = Depends(admin_only),
    store: DataStore = Depends(get_store),
    users: UserStore = Depends(get_user_store),
    clock: Clock = Depends(get_clock),
) -> admin.PickupPage:
    iso = (day or local_today(clock)).isoformat()
    return admin.list_pickups(store, users, iso, zone or None, status_ or None, page, page_size)


@router.get("/pickups/{pickup_id}", response_model=admin.PickupDetail)
def pickup_detail(
    pickup_id: str,
    _: CurrentUser = Depends(admin_only),
    store: DataStore = Depends(get_store),
    users: UserStore = Depends(get_user_store),
) -> admin.PickupDetail:
    return admin.pickup_detail(store, users, pickup_id)


class AssignRequest(BaseModel):
    collectorUid: str = Field(min_length=1, max_length=128)


@router.post("/pickups/{pickup_id}/assign", response_model=admin.PickupDetail)
def assign(
    pickup_id: str,
    body: AssignRequest,
    user: CurrentUser = Depends(admin_only),
    store: DataStore = Depends(get_store),
    users: UserStore = Depends(get_user_store),
    clock: Clock = Depends(get_clock),
    cache: admin.TTLCache = Depends(get_admin_cache),
) -> admin.PickupDetail:
    """Assign/reassign a collector (state machine). Demo admin: demo/synthetic households only."""
    result = admin.assign_pickup(store, users, clock, user.uid, pickup_id, body.collectorUid,
                                 demo_admin=is_demo_uid(user.uid))
    cache.clear()
    return result


@router.get("/users", response_model=list[UserProfile])
def users_list(
    role: Role | None = None,
    user: CurrentUser = Depends(admin_only),
    users: UserStore = Depends(get_user_store),
) -> list[UserProfile]:
    return admin.list_users(users, role, mask_real_emails=is_demo_uid(user.uid))


class StaffRequest(BaseModel):
    email: str = Field(min_length=3, max_length=120, pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
    name: str = Field(min_length=1, max_length=80)
    role: Literal["collector", "operator"]
    zones: list[str] = Field(default_factory=list, max_length=6)


@router.post("/staff", response_model=admin.StaffCreated, status_code=201)
def create_staff(
    body: StaffRequest,
    _: CurrentUser = Depends(deny_in_demo),
    identity: IdentityAdmin = Depends(get_identity),
    users: UserStore = Depends(get_user_store),
    cache: admin.TTLCache = Depends(get_admin_cache),
) -> admin.StaffCreated:
    """Create a collector/operator (real admin only). Returns a one-time password setup link."""
    created = admin.create_staff(identity, users, body.email, body.name, Role(body.role), body.zones)
    cache.clear()
    return created


class ZonesRequest(BaseModel):
    zones: list[str] = Field(min_length=1, max_length=6)


@router.patch("/users/{uid}/zones", response_model=UserProfile)
def set_zones(
    uid: str,
    body: ZonesRequest,
    _: CurrentUser = Depends(deny_in_demo),
    users: UserStore = Depends(get_user_store),
) -> UserProfile:
    return admin.set_collector_zones(users, uid, body.zones)


@router.get("/partners", response_model=list[admin.PartnerRow])
def partners(
    _: CurrentUser = Depends(admin_only),
    store: DataStore = Depends(get_store),
    clock: Clock = Depends(get_clock),
    cache: admin.TTLCache = Depends(get_admin_cache),
) -> list[admin.PartnerRow]:
    return cache.get_or_set(("partners",), lambda: admin.list_partners(store, clock))


class PartnerRequest(BaseModel):
    name: str = Field(min_length=2, max_length=60)


@router.post("/partners", response_model=admin.PartnerKey, status_code=201)
def create_partner(
    body: PartnerRequest,
    _: CurrentUser = Depends(deny_in_demo),
    store: DataStore = Depends(get_store),
    clock: Clock = Depends(get_clock),
    cache: admin.TTLCache = Depends(get_admin_cache),
) -> admin.PartnerKey:
    created = admin.create_partner(store, clock, body.name)
    cache.clear()
    return created


@router.post("/partners/{partner_id}/rotate-key", response_model=admin.PartnerKey)
def rotate_key(
    partner_id: str,
    _: CurrentUser = Depends(deny_in_demo),
    store: DataStore = Depends(get_store),
    clock: Clock = Depends(get_clock),
) -> admin.PartnerKey:
    return admin.rotate_partner_key(store, clock, partner_id)


class DemoKey(BaseModel):
    partnerId: str
    apiKey: str


@router.get("/partners/{partner_id}/demo-key", response_model=DemoKey)
async def demo_key(
    partner_id: str,
    _: CurrentUser = Depends(admin_only),
    reader: DemoKeyReader = Depends(get_demo_key_reader),
) -> DemoKey:
    """The DEMO partners' API key from Secret Manager (any other partner: 404)."""
    key = await run_in_threadpool(reader.read, partner_id)
    return DemoKey(partnerId=partner_id, apiKey=key)
