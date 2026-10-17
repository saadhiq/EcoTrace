"""Resident insights: household stats, eco score and points.

Everything here is a pure function of the household's CONFIRMED waste records
(never Gemini), so stats can be rebuilt at any time and never drift:
confirm() and the backfill script both call rebuild().

Eco score (0-100), across all processed bags:
    sorting   50 x average segregation   (good = 1, mixed = 0.5, poor = 0)
    recycling 30 x recyclable share      (recyclable quantity / total quantity)
    hazards   20 x safe-hazard share     (bags with no hazards, or hazards packed
                                          separately = segregation "good")
Points per processed bag: +10; +5 if segregation is "good"; +5 if the bag had
hazard flags and was "good" (hazardous items packed separately).
"""

import hashlib
import json
from collections import defaultdict
from datetime import datetime
from typing import TYPE_CHECKING

from app.models import (
    CategoryStat,
    HouseholdStats,
    LedgerEntry,
    PickupPoint,
    ScoreParts,
    WasteRecord,
    WasteRecordStatus,
)
from app.clock import COLOMBO
from app.segments import SEGMENT_VERSION, assign_segment
from app.taxonomy import CATEGORIES, SEGREGATION_QUALITIES

if TYPE_CHECKING:
    from app.store import DataStore

WEIGHT_SORTING = 50
WEIGHT_RECYCLING = 30
WEIGHT_HAZARDS = 20
SEGREGATION_VALUE = {"good": 1.0, "mixed": 0.5, "poor": 0.0}

POINTS_BAG = 10
POINTS_GOOD_SEGREGATION = 5
POINTS_HAZARDS_SEPARATED = 5

SCORE_EXPLANATION = (
    "50% sorting quality + 30% recyclable share + 20% safe hazard disposal, across all your processed bags."
)
TREND_POINTS = 12
TOP_PRODUCT_TYPES = 15


def normalize_type(text: str | None) -> str:
    """'Beverage_Bottles' -> 'beverage bottle' (lowercase, no underscores, naive singular)."""
    words = (text or "").lower().replace("_", " ").replace("-", " ").split()
    return " ".join(w[:-1] if len(w) > 3 and w.endswith("s") and not w.endswith("ss") else w for w in words)


def processed_day(record: WasteRecord) -> str | None:
    if record.processedAt is None:
        return record.pickupDate
    return record.processedAt.astimezone(COLOMBO).date().isoformat()


def _safe_hazards(record: WasteRecord) -> bool:
    return not record.hazardFlags or record.segregationQuality == "good"


def score_parts(records: list[WasteRecord]) -> ScoreParts | None:
    """Weighted eco-score parts for a set of confirmed records (None if empty)."""
    if not records:
        return None
    sorting = sum(SEGREGATION_VALUE.get(r.segregationQuality or "mixed", 0.5) for r in records) / len(records)
    quantity = sum(i.quantity for r in records for i in r.finalItems)
    recyclable = sum(i.quantity for r in records for i in r.finalItems if i.recyclable)
    recycling = recyclable / quantity if quantity else 0.0
    hazards = sum(1 for r in records if _safe_hazards(r)) / len(records)
    return ScoreParts(
        sorting=round(WEIGHT_SORTING * sorting, 1),
        recycling=round(WEIGHT_RECYCLING * recycling, 1),
        hazards=round(WEIGHT_HAZARDS * hazards, 1),
    )


def eco_score(records: list[WasteRecord]) -> int | None:
    parts = score_parts(records)
    if parts is None:
        return None
    return max(0, min(100, round(parts.sorting + parts.recycling + parts.hazards)))


def awards_for(record: WasteRecord) -> list[LedgerEntry]:
    """Ledger entries earned by one processed bag (deterministic ids => idempotent)."""
    at = record.processedAt or datetime.min
    entries = [LedgerEntry(id=f"{record.bagCode}-bag_processed", bagCode=record.bagCode,
                           reason="bag_processed", points=POINTS_BAG, at=at)]
    if record.segregationQuality == "good":
        entries.append(LedgerEntry(id=f"{record.bagCode}-good_segregation", bagCode=record.bagCode,
                                   reason="good_segregation", points=POINTS_GOOD_SEGREGATION, at=at))
        if record.hazardFlags:
            entries.append(LedgerEntry(id=f"{record.bagCode}-hazards_separated", bagCode=record.bagCode,
                                       reason="hazards_separated", points=POINTS_HAZARDS_SEPARATED, at=at))
    return entries


def compute_stats(records: list[WasteRecord], now: datetime) -> HouseholdStats:
    """Aggregate confirmed records into the household summary."""
    confirmed = [r for r in records if r.status == WasteRecordStatus.CONFIRMED]
    categories = {c: CategoryStat() for c in CATEGORIES}
    segregation = {q: 0 for q in SEGREGATION_QUALITIES}
    hazards: dict[str, int] = defaultdict(int)
    for record in confirmed:
        for item in record.finalItems:
            stat = categories[item.category]
            stat.items += 1
            stat.quantity += item.quantity
        segregation[record.segregationQuality or "mixed"] += 1
        for flag in record.hazardFlags:
            hazards[flag] += 1

    total_quantity = sum(c.quantity for c in categories.values())
    recyclable = sum(i.quantity for r in confirmed for i in r.finalItems if i.recyclable)

    by_pickup: dict[str, list[WasteRecord]] = defaultdict(list)
    for record in confirmed:
        by_pickup[record.pickupId or f"bag:{record.bagCode}"].append(record)
    trend = []
    for pickup_id, group in by_pickup.items():
        quantity = sum(i.quantity for r in group for i in r.finalItems)
        rec = sum(i.quantity for r in group for i in r.finalItems if i.recyclable)
        trend.append(PickupPoint(
            pickupId=pickup_id,
            date=max((processed_day(r) or "" for r in group), default="") or None,
            bags=len(group),
            quantity=quantity,
            recyclableShare=round(rec / quantity, 3) if quantity else None,
            ecoScore=eco_score(group),
        ))
    trend.sort(key=lambda p: (p.date or "", p.pickupId))

    product_types: dict[str, int] = defaultdict(int)
    monthly: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    for record in confirmed:
        month = (processed_day(record) or "")[:7]
        for item in record.finalItems:
            key = normalize_type(item.productType) or normalize_type(item.name)
            if key:
                product_types[key] += item.quantity
            if month:
                monthly[month][item.category] += item.quantity
    top_types = dict(sorted(product_types.items(), key=lambda kv: (-kv[1], kv[0]))[:TOP_PRODUCT_TYPES])
    days = sorted(d for d in (processed_day(r) for r in confirmed) if d)

    stats = HouseholdStats(
        categories=categories,
        totalItems=sum(c.items for c in categories.values()),
        totalQuantity=total_quantity,
        recyclableQuantity=recyclable,
        recyclableShare=round(recyclable / total_quantity, 3) if total_quantity else None,
        bagsProcessed=len(confirmed),
        pickupsProcessed=len(by_pickup),
        segregation=segregation,
        hazards=dict(sorted(hazards.items())),
        hazardBags=sum(1 for r in confirmed if r.hazardFlags),
        safeHazardBags=sum(1 for r in confirmed if r.hazardFlags and r.segregationQuality == "good"),
        ecoScore=eco_score(confirmed),
        scoreParts=score_parts(confirmed),
        points=sum(e.points for r in confirmed for e in awards_for(r)),
        byPickup=trend[-TREND_POINTS:],
        productTypes=top_types,
        monthly={m: dict(c) for m, c in sorted(monthly.items())},
        segment=assign_segment(
            {c: s.quantity for c, s in categories.items()},
            product_types,
            hazard_bags=sum(1 for r in confirmed if r.hazardFlags),
            good_bags=segregation["good"],
            bags=len(confirmed),
        ),
        segmentVersion=SEGMENT_VERSION,
        firstProcessed=days[0] if days else None,
        lastProcessed=days[-1] if days else None,
        lastUpdated=now,
    )
    return stats.model_copy(update={"statsHash": stats_hash(stats)})


def stats_hash(stats: HouseholdStats) -> str:
    """Fingerprint of the numbers tips are generated from (ignores timestamps)."""
    payload = tips_payload(stats)
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()[:16]


def tips_payload(stats: HouseholdStats) -> dict:
    """The ONLY data sent to Gemini for tips: aggregated numbers, no items/brands/PII."""
    return {
        "bagsProcessed": stats.bagsProcessed,
        "quantityByCategory": {k: v.quantity for k, v in stats.categories.items() if v.quantity},
        "recyclableShare": stats.recyclableShare,
        "segregation": stats.segregation,
        "hazardFlags": stats.hazards,
        "hazardBagsPackedSeparately": stats.safeHazardBags,
        "hazardBags": stats.hazardBags,
        "ecoScore": stats.ecoScore,
    }


def rebuild(
    store: "DataStore", now: datetime, household_id: str, pending: list[WasteRecord] | None = None
) -> tuple[HouseholdStats, list[LedgerEntry]]:
    """Stats + full ledger for a household from its confirmed records (plus `pending`,
    records about to be written in the same batch)."""
    by_code = {r.bagCode: r for r in store.list_confirmed_records(household_id)}
    for record in pending or []:
        by_code[record.bagCode] = record
    records = list(by_code.values())
    missing = [r.pickupId for r in records if r.pickupDate is None and r.pickupId]
    if missing:
        dates = {pid: p.date for pid, p in store.get_pickups(missing).items()}
        records = [
            r.model_copy(update={"pickupDate": dates.get(r.pickupId or "")}) if r.pickupDate is None else r
            for r in records
        ]
    ledger = [entry for record in records for entry in awards_for(record)]
    return compute_stats(records, now), ledger
