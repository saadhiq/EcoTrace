"""Resident insights services: Gemini tips (cached), pickup details, consent."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel

from app.ai.gemini import AiError
from app.ai.tips import STATIC_TIPS, TipGenerator
from app.clock import Clock
from app.errors import DomainError
from app.insights import SCORE_EXPLANATION, tips_payload
from app.models import ConsentEntry, Household, Tip, TipsCache, WasteItem
from app.ratelimit import RateLimiter
from app.store import DataStore

# Bump when the consent explanation shown to residents changes.
CONSENT_TEXT_VERSION = "v1"

TipsSource = Literal["gemini", "cache", "fallback", "starter"]


class TipsResponse(BaseModel):
    lang: str
    tips: list[Tip]
    source: TipsSource
    model: str | None = None
    generatedAt: datetime | None = None
    latencyMs: int | None = None


def _from_cache(cache: TipsCache, source: TipsSource) -> TipsResponse:
    return TipsResponse(
        lang=cache.lang, tips=cache.tips, source=source, model=cache.model,
        generatedAt=cache.generatedAt, latencyMs=cache.latencyMs,
    )


def get_tips(
    store: DataStore,
    generator: TipGenerator,
    limiter: RateLimiter,
    clock: Clock,
    uid: str,
    lang: str,
) -> TipsResponse:
    """Cached per household + language; Gemini is called only when stats changed."""
    stats = store.get_stats(uid)
    if stats is None or stats.bagsProcessed == 0:
        return TipsResponse(lang=lang, tips=STATIC_TIPS[lang], source="starter")

    cached = store.get_tips(uid, lang)
    if cached is not None and cached.statsHash == stats.statsHash:
        return _from_cache(cached, "cache")

    def fallback() -> TipsResponse:
        # Prefer older personalised tips over generic ones; don't cache fallbacks.
        if cached is not None:
            return _from_cache(cached, "fallback")
        return TipsResponse(lang=lang, tips=STATIC_TIPS[lang], source="fallback")

    if not limiter.allow(uid):
        return fallback()
    try:
        tips, latency_ms = generator.generate(tips_payload(stats), lang)
    except AiError:
        return fallback()
    cache = TipsCache(
        lang=lang, tips=tips, statsHash=stats.statsHash, model=generator.model,
        generatedAt=clock.now(), latencyMs=latency_ms,
    )
    store.save_tips(uid, cache)
    return _from_cache(cache, "gemini")


# --- pickup details (what was found in each bag; no photos, no AI internals) ---


class BagDetail(BaseModel):
    code: str
    slot: int
    status: str
    items: list[WasteItem]
    segregationQuality: str | None
    hazardFlags: list[str]


class PickupDetails(BaseModel):
    pickupId: str
    date: str
    status: str
    bags: list[BagDetail]


def pickup_details(store: DataStore, uid: str, pickup_id: str) -> PickupDetails:
    pickup = store.get_pickup(pickup_id)
    if pickup is None or pickup.residentUid != uid:
        raise DomainError(404, "pickup_not_found")
    bags = store.get_bags(pickup.bagCodes)
    records = store.get_waste_records(pickup.bagCodes)
    details = []
    for slot, code in enumerate(pickup.bagCodes, start=1):
        bag = bags.get(code)
        if bag is None or bag.pickupId != pickup.id:
            continue  # released back to the resident (missing / cancelled)
        record = records.get(code)
        confirmed = record is not None and record.status == "confirmed"
        details.append(
            BagDetail(
                code=code,
                slot=slot,
                status=bag.status,
                items=record.finalItems if confirmed else [],
                segregationQuality=record.segregationQuality if confirmed else None,
                hazardFlags=record.hazardFlags if confirmed else [],
            )
        )
    return PickupDetails(pickupId=pickup.id, date=pickup.date, status=pickup.status, bags=details)


# --- consent ---


class ConsentView(BaseModel):
    dataSharing: bool
    updatedAt: datetime | None
    textVersion: str
    history: list[ConsentEntry]


def consent_view(store: DataStore, household: Household) -> ConsentView:
    return ConsentView(
        dataSharing=household.consent.dataSharing,
        updatedAt=household.consent.updatedAt,
        textVersion=CONSENT_TEXT_VERSION,
        history=store.list_consent_history(household.id),
    )


def consent_change(household: Household, value: bool, clock: Clock, by: str) -> tuple[Household, ConsentEntry] | None:
    """The updated household + history entry, or None if nothing changes."""
    if household.consent.dataSharing == value:
        return None
    now = clock.now()
    updated = household.model_copy(
        update={"consent": household.consent.model_copy(update={"dataSharing": value, "updatedAt": now})}
    )
    return updated, ConsentEntry(value=value, at=now, by=by, textVersion=CONSENT_TEXT_VERSION)


def set_consent(store: DataStore, clock: Clock, household: Household, value: bool, by: str) -> Household:
    change = consent_change(household, value, clock, by)
    if change is None:
        return household
    updated, entry = change
    store.commit([], [], households=[updated], consent=[(household.id, entry)])
    return updated


__all__ = ["SCORE_EXPLANATION"]
