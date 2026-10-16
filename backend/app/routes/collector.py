"""Collector endpoints: day list, accept, scan, complete, missed, handover."""

from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field

from app import collector
from app.auth import get_user_store, require_role
from app.clock import Clock, local_today
from app.demo import is_demo_uid
from app.deps import get_clock, get_store
from app.models import CurrentUser, Role
from app.store import DataStore
from app.users import UserStore

router = APIRouter(prefix="/collector")
collector_only = require_role(Role.COLLECTOR)


class Caller(BaseModel):
    uid: str
    zones: list[str]
    isDemo: bool


def get_caller(
    user: CurrentUser = Depends(collector_only), users: UserStore = Depends(get_user_store)
) -> Caller:
    profile = users.get(user.uid)
    return Caller(uid=user.uid, zones=profile.zones if profile else [], isDemo=is_demo_uid(user.uid))


class DayView(BaseModel):
    date: str
    zones: list[str]
    available: list[collector.CollectorPickup]
    mine: list[collector.CollectorPickup]


class ScanRequest(BaseModel):
    code: str = Field(min_length=1, max_length=40)


class SimulateRequest(BaseModel):
    slot: int = Field(ge=1, le=5)


class CompleteRequest(BaseModel):
    missingReason: str | None = Field(default=None, max_length=collector.MAX_REASON)


class MissedRequest(BaseModel):
    reason: str = Field(min_length=1, max_length=collector.MAX_REASON)


@router.get("/pickups", response_model=DayView)
def day_view(
    day: date | None = Query(default=None, alias="date"),
    caller: Caller = Depends(get_caller),
    store: DataStore = Depends(get_store),
    clock: Clock = Depends(get_clock),
) -> DayView:
    iso = (day or local_today(clock)).isoformat()
    available, mine = collector.list_day(store, caller.uid, caller.zones, iso)
    return DayView(date=iso, zones=caller.zones, available=available, mine=mine)


@router.get("/pickups/{pickup_id}", response_model=collector.CollectorPickupDetail)
def pickup_detail(
    pickup_id: str, caller: Caller = Depends(get_caller), store: DataStore = Depends(get_store)
) -> collector.CollectorPickupDetail:
    return collector.get_pickup(store, caller.uid, caller.zones, pickup_id)


@router.post("/pickups/{pickup_id}/accept", response_model=collector.CollectorPickupDetail)
def accept(
    pickup_id: str,
    caller: Caller = Depends(get_caller),
    store: DataStore = Depends(get_store),
    clock: Clock = Depends(get_clock),
) -> collector.CollectorPickupDetail:
    return collector.accept(store, clock, caller.uid, caller.zones, pickup_id)


@router.post("/pickups/{pickup_id}/scan", response_model=collector.ScanResult)
def scan(
    pickup_id: str,
    body: ScanRequest,
    caller: Caller = Depends(get_caller),
    store: DataStore = Depends(get_store),
    clock: Clock = Depends(get_clock),
) -> collector.ScanResult:
    return collector.scan(store, clock, caller.uid, pickup_id, body.code)


@router.post("/pickups/{pickup_id}/simulate-scan", response_model=collector.ScanResult)
def simulate_scan(
    pickup_id: str,
    body: SimulateRequest,
    caller: Caller = Depends(get_caller),
    store: DataStore = Depends(get_store),
    clock: Clock = Depends(get_clock),
) -> collector.ScanResult:
    """For the shared demo collector only, so judges can try the flow without a printed QR."""
    if not caller.isDemo:
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="demo_only")
    return collector.simulate_scan(store, clock, caller.uid, pickup_id, body.slot)


@router.post("/pickups/{pickup_id}/complete", response_model=collector.CollectorPickupDetail)
def complete(
    pickup_id: str,
    body: CompleteRequest,
    caller: Caller = Depends(get_caller),
    store: DataStore = Depends(get_store),
    clock: Clock = Depends(get_clock),
) -> collector.CollectorPickupDetail:
    return collector.complete(store, clock, caller.uid, pickup_id, body.missingReason)


@router.post("/pickups/{pickup_id}/missed", response_model=collector.CollectorPickupDetail)
def missed(
    pickup_id: str,
    body: MissedRequest,
    caller: Caller = Depends(get_caller),
    store: DataStore = Depends(get_store),
    clock: Clock = Depends(get_clock),
) -> collector.CollectorPickupDetail:
    return collector.mark_missed(store, clock, caller.uid, pickup_id, body.reason)


@router.get("/handover", response_model=list[collector.HandoverPickup])
def handover(
    caller: Caller = Depends(get_caller), store: DataStore = Depends(get_store)
) -> list[collector.HandoverPickup]:
    return collector.handover_list(store, caller.uid)


@router.post("/handover/scan", response_model=collector.HandoverScanResult)
def handover_scan(
    body: ScanRequest,
    caller: Caller = Depends(get_caller),
    store: DataStore = Depends(get_store),
    clock: Clock = Depends(get_clock),
) -> collector.HandoverScanResult:
    return collector.handover_scan(store, clock, caller.uid, body.code)
