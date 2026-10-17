"""Warehouse operator: classify bag photos with Gemini, review, confirm.

analyze() stores photos + a DRAFT wasteRecords/{code} holding the AI result
(server-side, so confirm() can measure human edits against the real model
output). confirm() writes the final record, bag -> processed and, when it was
the pickup's last bag, pickup -> processed, all in one batch.
"""

from datetime import datetime

from pydantic import BaseModel, Field

from app.ai.classifier import AiError, Classifier
from app.insights import awards_for, rebuild
from app.clock import Clock
from app.errors import DomainError
from app.models import (
    AiItem,
    AiResult,
    BagStatus,
    PickupStatus,
    TokenUsage,
    WasteItem,
    WasteRecord,
    WasteRecordStatus,
)
from app.photos import PhotoStore, validate_photos
from app.services import attached_bags, route_stop
from app.store import DataStore
from app.taxonomy import HazardFlag, SegregationQuality
from app.transitions import advance_bag, advance_pickup

DONE = {BagStatus.PROCESSED}
EDIT_FIELDS = ("name", "category", "material", "productType", "brand", "quantity", "recyclable")


# --- views ---


class QueueItem(BaseModel):
    code: str
    pickupId: str | None
    zone: str | None
    pickupDate: str | None
    arrivedAt: datetime | None
    hasDraft: bool


class BagView(BaseModel):
    code: str
    status: BagStatus
    pickupId: str | None
    zone: str | None
    pickupDate: str | None
    bagsInPickup: int
    processedInPickup: int
    record: WasteRecord | None


class AnalyzeResult(BaseModel):
    result: AiResult
    model: str
    latencyMs: int
    tokenUsage: TokenUsage
    photoCount: int


class FinalItem(WasteItem):
    # Index of the AI item this row came from (None = added by the operator).
    aiIndex: int | None = Field(default=None, ge=0)


class ConfirmResult(BaseModel):
    record: WasteRecord
    pickupProcessed: bool


def _arrived_at(history: list) -> datetime | None:  # noqa: ANN001
    events = [e.at for e in history if e.status == BagStatus.AT_WAREHOUSE]
    return events[-1] if events else None


# --- reads ---


def queue(store: DataStore) -> list[QueueItem]:
    """Bags waiting at the warehouse, oldest arrival first. No resident PII."""
    bags = store.list_bags_by_status(BagStatus.AT_WAREHOUSE)
    pickups = {pid: store.get_pickup(pid) for pid in {b.pickupId for b in bags if b.pickupId}}
    drafts = store.get_waste_records([b.code for b in bags])
    items = []
    for bag in bags:
        pickup = pickups.get(bag.pickupId) if bag.pickupId else None
        items.append(
            QueueItem(
                code=bag.code,
                pickupId=bag.pickupId,
                zone=pickup.zone if pickup else None,
                pickupDate=pickup.date if pickup else None,
                arrivedAt=_arrived_at(bag.statusHistory),
                hasDraft=bag.code in drafts,
            )
        )
    return sorted(items, key=lambda i: (i.arrivedAt is None, i.arrivedAt or datetime.max, i.code))


def _bag(store: DataStore, code: str):  # noqa: ANN202
    bag = store.get_bags([code]).get(code)
    if bag is None:
        raise DomainError(404, "unknown_code")
    return bag


def get_bag(store: DataStore, code: str) -> BagView:
    bag = _bag(store, code)
    pickup = store.get_pickup(bag.pickupId) if bag.pickupId else None
    siblings = attached_bags(store, pickup) if pickup else [bag]
    return BagView(
        code=bag.code,
        status=bag.status,
        pickupId=bag.pickupId,
        zone=pickup.zone if pickup else None,
        pickupDate=pickup.date if pickup else None,
        bagsInPickup=len(siblings),
        processedInPickup=sum(1 for b in siblings if b.status in DONE),
        record=store.get_waste_records([code]).get(code),
    )


def _require_at_warehouse(store: DataStore, code: str):  # noqa: ANN202
    bag = _bag(store, code)
    if bag.status == BagStatus.PROCESSED:
        raise DomainError(409, "already_processed")
    if bag.status != BagStatus.AT_WAREHOUSE:
        raise DomainError(409, "not_at_warehouse")
    return bag


# --- analyze ---


def analyze(
    store: DataStore,
    photos_store: PhotoStore,
    classifier: Classifier,
    clock: Clock,
    code: str,
    blobs: list[bytes],
) -> AnalyzeResult:
    """Store photos, run Gemini, save a draft. Raises DomainError(502/504) on AI failure."""
    bag = _require_at_warehouse(store, code)
    photos = validate_photos(blobs)
    try:
        paths = photos_store.save(code, photos, clock.now())
    except Exception as exc:  # noqa: BLE001 - storage outage must not break the page
        raise DomainError(503, "photo_upload_failed") from exc

    previous = store.get_waste_records([code]).get(code)
    draft = WasteRecord(
        bagCode=code,
        householdId=bag.householdId,
        pickupId=bag.pickupId,
        status=WasteRecordStatus.DRAFT,
        photoPaths=[*(previous.photoPaths if previous else []), *paths],
        model=classifier.model,
        analyzedAt=clock.now(),
    )
    try:
        outcome = classifier.classify([(p.data, p.mime) for p in photos])
    except AiError as exc:
        store.save_waste_record(draft.model_copy(update={"aiError": exc.kind}))
        status = 502 if exc.kind == "invalid_output" else 504
        raise DomainError(status, f"ai_{exc.kind}") from exc

    store.save_waste_record(
        draft.model_copy(
            update={
                "aiResult": outcome.result,
                "model": outcome.model,
                "latencyMs": outcome.latency_ms,
                "tokenUsage": outcome.token_usage,
            }
        )
    )
    return AnalyzeResult(
        result=outcome.result,
        model=outcome.model,
        latencyMs=outcome.latency_ms,
        tokenUsage=outcome.token_usage,
        photoCount=len(paths),
    )


# --- confirm ---


def count_edits(
    ai: AiResult | None,
    items: list[FinalItem],
    quality: SegregationQuality,
    hazards: list[HazardFlag],
) -> int:
    """Items added + removed + changed, plus bag-level changes.

    Each final row says which AI item it came from (aiIndex), so renaming an
    item counts as one change, not a removal plus an addition.
    """
    if ai is None:
        return len(items)
    seen: set[int] = set()
    edits = 0
    for item in items:
        if item.aiIndex is None:
            edits += 1  # added
            continue
        if item.aiIndex >= len(ai.items) or item.aiIndex in seen:
            raise DomainError(422, "invalid_ai_index")
        seen.add(item.aiIndex)
        source: AiItem = ai.items[item.aiIndex]
        if any(_norm(getattr(item, f)) != _norm(getattr(source, f)) for f in EDIT_FIELDS):
            edits += 1  # modified
    edits += len(ai.items) - len(seen)  # removed
    edits += quality != ai.segregationQuality
    edits += set(hazards) != set(ai.hazardFlags)
    return edits


def _norm(value: object) -> object:
    return value.strip().lower() if isinstance(value, str) else value


def confirm(
    store: DataStore,
    clock: Clock,
    operator_uid: str,
    code: str,
    items: list[FinalItem],
    quality: SegregationQuality,
    hazards: list[HazardFlag],
) -> ConfirmResult:
    bag = _require_at_warehouse(store, code)
    if not items:
        raise DomainError(422, "no_items")
    draft = store.get_waste_records([code]).get(code)
    ai = draft.aiResult if draft else None
    edits = count_edits(ai, items, quality, hazards)
    now = clock.now()

    record = WasteRecord(
        bagCode=code,
        householdId=bag.householdId,
        pickupId=bag.pickupId,
        status=WasteRecordStatus.CONFIRMED,
        photoPaths=draft.photoPaths if draft else [],
        aiResult=ai,
        aiError=draft.aiError if draft else None,
        model=draft.model if draft else None,
        latencyMs=draft.latencyMs if draft else None,
        tokenUsage=draft.tokenUsage if draft else None,
        analyzedAt=draft.analyzedAt if draft else None,
        finalItems=[WasteItem(**i.model_dump(exclude={"aiIndex"})) for i in items],
        segregationQuality=quality,
        hazardFlags=sorted(set(hazards)),
        edited=ai is None or edits > 0,
        editCount=edits,
        source="manual" if ai is None else ("ai_edited" if edits else "ai"),
        operatorUid=operator_uid,
        processedAt=now,
    )
    processed_bag = advance_bag(bag, BagStatus.PROCESSED, by=operator_uid, clock=clock)

    pickup = store.get_pickup(bag.pickupId) if bag.pickupId else None
    if pickup is not None:
        record = record.model_copy(update={"pickupDate": pickup.date})
    pickups, routes = [], []
    pickup_done = False
    if pickup is not None:
        others = [b for b in attached_bags(store, pickup) if b.code != code]
        pickup_done = pickup.status == PickupStatus.DELIVERED and all(b.status in DONE for b in others)
        if pickup_done:
            pickup = advance_pickup(pickup, PickupStatus.PROCESSED, by=operator_uid, clock=clock)
            pickups.append(pickup)
            if pickup.collectorUid:
                household = store.get_household(pickup.householdId)
                routes.append(route_stop(pickup, household, [*others, processed_bag], clock))
    # Household stats are rebuilt from all confirmed records and written in the
    # SAME batch, so they are always in sync with wasteRecords.
    stats, _ = rebuild(store, now, bag.householdId, pending=[record])
    store.commit(
        pickups,
        [processed_bag],
        routes,
        [record],
        stats=[(bag.householdId, stats)],
        ledger=[(bag.householdId, entry) for entry in awards_for(record)],
    )
    return ConfirmResult(record=record, pickupProcessed=pickup_done)
