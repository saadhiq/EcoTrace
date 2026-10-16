"""Shared domain models (also the Firestore document shapes)."""

from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class Role(StrEnum):
    RESIDENT = "resident"
    COLLECTOR = "collector"
    OPERATOR = "operator"
    ADMIN = "admin"


class CurrentUser(BaseModel):
    """The caller, as described by a verified Firebase ID token."""

    uid: str
    email: str | None = None
    name: str | None = None
    role: Role | None = None


class UserProfile(BaseModel):
    """Mirror of users/{uid} in Firestore."""

    uid: str
    name: str
    email: str | None = None
    role: Role
    createdAt: datetime | None = None
    # Collectors only: the zones they cover.
    zones: list[str] = Field(default_factory=list)


# --- Resident flow ---


class BagStatus(StrEnum):
    ISSUED = "issued"
    SCHEDULED = "scheduled"
    COLLECTED = "collected"
    AT_WAREHOUSE = "at_warehouse"
    PROCESSED = "processed"


class PickupStatus(StrEnum):
    REQUESTED = "requested"
    ASSIGNED = "assigned"
    COLLECTED = "collected"
    DELIVERED = "delivered"
    PROCESSED = "processed"
    CANCELLED = "cancelled"
    MISSED = "missed"


CANCELLABLE_PICKUP_STATUSES = {PickupStatus.REQUESTED, PickupStatus.ASSIGNED}


class TimeSlot(StrEnum):
    MORNING = "morning"
    AFTERNOON = "afternoon"


class StatusEvent(BaseModel):
    status: str
    at: datetime
    by: str


class Consent(BaseModel):
    dataSharing: bool = False
    updatedAt: datetime | None = None


class Household(BaseModel):
    """households/{id}. The id is the owner's uid (one household per resident)."""

    id: str
    ownerUid: str
    name: str
    phone: str
    addressLine: str
    zone: str
    lat: float | None = None
    lng: float | None = None
    consent: Consent = Field(default_factory=Consent)
    createdAt: datetime


class Bag(BaseModel):
    """bags/{code}."""

    code: str
    householdId: str
    ownerUid: str
    status: BagStatus
    pickupId: str | None = None
    # Set when a collector scans the bag (powers the warehouse handover).
    collectorUid: str | None = None
    issuedAt: datetime
    statusHistory: list[StatusEvent] = Field(default_factory=list)


class Pickup(BaseModel):
    """pickups/{id}."""

    id: str
    householdId: str
    residentUid: str
    zone: str
    date: str  # YYYY-MM-DD, Asia/Colombo
    timeSlot: TimeSlot
    bagCodes: list[str]
    notes: str = ""
    status: PickupStatus
    collectorUid: str | None = None
    statusHistory: list[StatusEvent] = Field(default_factory=list)
    createdAt: datetime
    assignedAt: datetime | None = None
    collectedAt: datetime | None = None
    deliveredAt: datetime | None = None
    missedReason: str | None = None
    # Partial completion: why some bags were not collected.
    missingBagsReason: str | None = None


class RouteStop(BaseModel):
    """routes/{pickupId}: code-free mirror of an assigned pickup.

    Lets a collector's browser listen live to their route (Firestore rules
    can't hide fields, so pickups themselves would leak bag codes).
    """

    pickupId: str
    collectorUid: str
    date: str
    timeSlot: TimeSlot
    status: PickupStatus
    zone: str
    householdName: str
    addressLine: str
    bagCount: int
    scannedCount: int
    updatedAt: datetime


def to_doc(model: BaseModel, id_field: str) -> dict[str, Any]:
    """Firestore document data: the model minus its id field (the doc id)."""
    return model.model_dump(mode="python", exclude={id_field})
