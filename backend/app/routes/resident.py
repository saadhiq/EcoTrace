"""Resident endpoints: household, bags, pickups. All writes go through here."""

from datetime import date

from fastapi import APIRouter, Depends, status
from pydantic import BaseModel, Field

from app import services
from app.auth import require_role
from app.clock import Clock
from app.deps import get_clock, get_store
from app.models import Bag, CurrentUser, Household, Pickup, Role, TimeSlot
from app.store import DataStore
from app.zones import ZONES, Zone

router = APIRouter()
resident = require_role(Role.RESIDENT)

PHONE_PATTERN = r"^\+?[0-9][0-9 \-]{6,18}$"


class HouseholdCreate(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    phone: str = Field(pattern=PHONE_PATTERN)
    addressLine: str = Field(min_length=1, max_length=200)
    zone: str
    lat: float | None = Field(default=None, ge=-90, le=90)
    lng: float | None = Field(default=None, ge=-180, le=180)


class HouseholdPatch(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=80)
    phone: str | None = Field(default=None, pattern=PHONE_PATTERN)
    addressLine: str | None = Field(default=None, min_length=1, max_length=200)
    zone: str | None = None
    lat: float | None = Field(default=None, ge=-90, le=90)
    lng: float | None = Field(default=None, ge=-180, le=180)
    dataSharing: bool | None = None


class HouseholdCreated(BaseModel):
    household: Household
    bags: list[Bag]


class PickupCreate(BaseModel):
    date: date
    timeSlot: TimeSlot
    bagCodes: list[str] = Field(min_length=1, max_length=services.MAX_BAGS_PER_PICKUP)
    notes: str = Field(default="", max_length=280)


@router.get("/zones", response_model=list[Zone])
def zones() -> list[Zone]:
    return ZONES


@router.post("/households", response_model=HouseholdCreated, status_code=status.HTTP_201_CREATED)
def create_household(
    body: HouseholdCreate,
    user: CurrentUser = Depends(resident),
    store: DataStore = Depends(get_store),
    clock: Clock = Depends(get_clock),
) -> HouseholdCreated:
    household, bags = services.create_household(
        store,
        clock,
        user.uid,
        name=body.name.strip(),
        phone=body.phone.strip(),
        address_line=body.addressLine.strip(),
        zone=body.zone,
        lat=body.lat,
        lng=body.lng,
    )
    return HouseholdCreated(household=household, bags=bags)


@router.get("/households/me", response_model=Household)
def my_household(
    user: CurrentUser = Depends(resident), store: DataStore = Depends(get_store)
) -> Household:
    return services.get_household(store, user.uid)


@router.patch("/households/me", response_model=Household)
def update_my_household(
    body: HouseholdPatch,
    user: CurrentUser = Depends(resident),
    store: DataStore = Depends(get_store),
    clock: Clock = Depends(get_clock),
) -> Household:
    return services.update_household(store, clock, user.uid, body.model_dump(exclude_unset=True))


@router.get("/bags/mine", response_model=list[Bag])
def my_bags(user: CurrentUser = Depends(resident), store: DataStore = Depends(get_store)) -> list[Bag]:
    return services.list_bags(store, user.uid)


@router.post("/bags/request-more", response_model=list[Bag], status_code=status.HTTP_201_CREATED)
def request_more_bags(
    user: CurrentUser = Depends(resident),
    store: DataStore = Depends(get_store),
    clock: Clock = Depends(get_clock),
) -> list[Bag]:
    return services.request_more_bags(store, clock, user.uid)


@router.post("/pickups", response_model=Pickup, status_code=status.HTTP_201_CREATED)
def schedule_pickup(
    body: PickupCreate,
    user: CurrentUser = Depends(resident),
    store: DataStore = Depends(get_store),
    clock: Clock = Depends(get_clock),
) -> Pickup:
    return services.schedule_pickup(
        store,
        clock,
        user.uid,
        pickup_date=body.date,
        time_slot=body.timeSlot,
        bag_codes=[code.strip().upper() for code in body.bagCodes],
        notes=body.notes,
    )


@router.get("/pickups/mine", response_model=list[Pickup])
def my_pickups(
    user: CurrentUser = Depends(resident), store: DataStore = Depends(get_store)
) -> list[Pickup]:
    return services.list_pickups(store, user.uid)


@router.post("/pickups/{pickup_id}/cancel", response_model=Pickup)
def cancel_pickup(
    pickup_id: str,
    user: CurrentUser = Depends(resident),
    store: DataStore = Depends(get_store),
    clock: Clock = Depends(get_clock),
) -> Pickup:
    return services.cancel_pickup(store, clock, user.uid, pickup_id)
