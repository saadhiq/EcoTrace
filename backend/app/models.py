"""Shared domain models (also the Firestore document shapes)."""

from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field

from app.taxonomy import Category, HazardFlag, SegregationQuality


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
    isSynthetic: bool = False


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
    isSynthetic: bool = False


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
    # Seeded demo data; excluded from analytics and the AI benchmark.
    isSynthetic: bool = False


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
    isSynthetic: bool = False


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


# --- Warehouse / AI classification ---


class WasteItem(BaseModel):
    """One item in a bag, as confirmed by the operator."""

    name: str = Field(min_length=1, max_length=80)
    category: Category
    material: str = Field(default="", max_length=60)
    productType: str = Field(default="", max_length=60)
    brand: str | None = Field(default=None, max_length=60)
    quantity: int = Field(default=1, ge=1, le=999)
    recyclable: bool = False


class AiItem(WasteItem):
    """An item as returned by Gemini (adds the model's confidence)."""

    confidence: float = Field(default=0.5, ge=0, le=1)


class AiResult(BaseModel):
    """Gemini's structured output for one bag (validated and normalised)."""

    items: list[AiItem]
    segregationQuality: SegregationQuality
    hazardFlags: list[HazardFlag] = Field(default_factory=list)
    notes: str = ""


class TokenUsage(BaseModel):
    prompt: int = 0
    output: int = 0
    thoughts: int = 0
    total: int = 0


class WasteRecordStatus(StrEnum):
    DRAFT = "draft"
    CONFIRMED = "confirmed"


class WasteRecord(BaseModel):
    """wasteRecords/{bagCode}: AI result kept next to the human-reviewed items."""

    bagCode: str
    householdId: str
    pickupId: str | None
    status: WasteRecordStatus
    photoPaths: list[str] = Field(default_factory=list)
    aiResult: AiResult | None = None
    aiError: str | None = None
    model: str | None = None
    latencyMs: int | None = None
    tokenUsage: TokenUsage | None = None
    analyzedAt: datetime | None = None
    # Set on confirm:
    finalItems: list[WasteItem] = Field(default_factory=list)
    segregationQuality: SegregationQuality | None = None
    hazardFlags: list[HazardFlag] = Field(default_factory=list)
    edited: bool = False
    editCount: int = 0
    source: str | None = None  # ai | ai_edited | manual
    operatorUid: str | None = None
    processedAt: datetime | None = None
    # Denormalised for insights (trend by pickup date).
    pickupDate: str | None = None
    isSynthetic: bool = False
    # Development/test run: kept for audit, excluded from insights and AI-quality metrics.
    isTest: bool = False
    # Operator edits vs the AI result (set on confirm; None on older records).
    itemsAdded: int | None = None
    itemsRemoved: int | None = None
    itemsModified: int | None = None


# --- Resident insights ---


class CategoryStat(BaseModel):
    items: int = 0  # distinct item rows
    quantity: int = 0


class ScoreParts(BaseModel):
    """Eco-score components, already weighted (sum = ecoScore)."""

    sorting: float
    recycling: float
    hazards: float


class PickupPoint(BaseModel):
    """One point of the trend chart (one processed pickup), dated by processedAt."""

    pickupId: str
    date: str | None  # Colombo date the pickup's last bag was processed
    bags: int
    quantity: int
    recyclableShare: float | None
    ecoScore: int | None


class HouseholdStats(BaseModel):
    """households/{id}/stats/summary: rebuilt from confirmed wasteRecords."""

    categories: dict[str, CategoryStat] = Field(default_factory=dict)
    totalItems: int = 0
    totalQuantity: int = 0
    recyclableQuantity: int = 0
    recyclableShare: float | None = None
    bagsProcessed: int = 0
    pickupsProcessed: int = 0
    segregation: dict[str, int] = Field(default_factory=dict)
    hazards: dict[str, int] = Field(default_factory=dict)
    hazardBags: int = 0
    safeHazardBags: int = 0
    ecoScore: int | None = None
    scoreParts: ScoreParts | None = None
    points: int = 0
    byPickup: list[PickupPoint] = Field(default_factory=list)
    # Normalised productType -> quantity (top 15), for swaps + segments.
    productTypes: dict[str, int] = Field(default_factory=dict)
    # YYYY-MM (processedAt, Colombo) -> {category: quantity}, for partner insights.
    monthly: dict[str, dict[str, int]] = Field(default_factory=dict)
    segment: str | None = None
    segmentVersion: str | None = None
    # Admin overview: zone, synthetic household flag, totals from real (non-synthetic) records only.
    zone: str | None = None
    isSynthetic: bool = False
    realOnly: dict = Field(default_factory=dict)
    firstProcessed: str | None = None
    lastProcessed: str | None = None
    statsHash: str = ""
    lastUpdated: datetime | None = None


class LedgerEntry(BaseModel):
    """households/{id}/pointsLedger/{id}: id = f"{bagCode}-{reason}" (idempotent)."""

    id: str
    bagCode: str
    reason: str
    points: int
    at: datetime


class Tip(BaseModel):
    title: str = Field(max_length=80)
    body: str = Field(max_length=400)
    category: Category


class TipsCache(BaseModel):
    """households/{id}/tips/{lang}."""

    lang: str
    tips: list[Tip]
    statsHash: str
    model: str
    generatedAt: datetime
    latencyMs: int | None = None


class ConsentEntry(BaseModel):
    """households/{id}/consentHistory/{auto}."""

    value: bool
    at: datetime
    by: str
    textVersion: str


# --- Partners & swaps ---


class Partner(BaseModel):
    """partners/{id}. Only a SHA-256 hash of the API key is stored."""

    id: str
    name: str
    apiKeyHash: str
    keyPrefix: str
    active: bool = True
    createdAt: datetime
    isSynthetic: bool = False


class CatalogItem(BaseModel):
    """partners/{id}/catalog/{sku}."""

    sku: str
    name: str
    category: Category
    tags: list[str] = Field(default_factory=list)
    replaces: list[str] = Field(default_factory=list)  # waste productTypes it substitutes
    ecoBenefit: str
    price: float
    url: str


class SwapPick(BaseModel):
    sku: str
    partnerId: str
    partnerName: str
    name: str
    category: Category
    ecoBenefit: str
    price: float
    url: str
    reason: str


class SwapsCache(BaseModel):
    """households/{id}/swaps/current (API only; deleted when consent is withdrawn)."""

    picks: list[SwapPick]
    statsHash: str
    catalogVersion: str
    model: str | None
    source: str  # gemini | fallback
    generatedAt: datetime
    latencyMs: int | None = None
