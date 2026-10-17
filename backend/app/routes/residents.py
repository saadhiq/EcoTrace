"""Resident insights endpoints: tips, pickup details, data-sharing consent."""

from functools import lru_cache
from typing import Literal

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel
from starlette.concurrency import run_in_threadpool

from app import recommendations, residents, services
from app.ai.tips import GeminiTipGenerator, TipGenerator
from app.recommendations import GeminiRanker, Ranker
from app.auth import require_role
from app.clock import Clock
from app.deps import get_clock, get_store
from app.models import CurrentUser, Role
from app.ratelimit import RateLimiter
from app.store import DataStore

router = APIRouter()
resident_only = require_role(Role.RESIDENT)


@lru_cache
def _tip_generator() -> GeminiTipGenerator:
    return GeminiTipGenerator()


def get_tip_generator() -> TipGenerator:
    return _tip_generator()


@lru_cache
def _ranker() -> GeminiRanker:
    return GeminiRanker()


def get_ranker() -> Ranker:
    return _ranker()


def get_tips_limiter(request: Request) -> RateLimiter:
    return request.app.state.tips_limiter


class ConsentRequest(BaseModel):
    dataSharing: bool


@router.post("/residents/me/tips", response_model=residents.TipsResponse)
async def tips(
    lang: Literal["en", "si", "ta"] = Query(default="en"),
    user: CurrentUser = Depends(resident_only),
    store: DataStore = Depends(get_store),
    generator: TipGenerator = Depends(get_tip_generator),
    limiter: RateLimiter = Depends(get_tips_limiter),
    clock: Clock = Depends(get_clock),
) -> residents.TipsResponse:
    """3 personalised tips from aggregated stats (cached until the stats change)."""
    return await run_in_threadpool(residents.get_tips, store, generator, limiter, clock, user.uid, lang)


@router.get("/residents/me/pickups/{pickup_id}/details", response_model=residents.PickupDetails)
def pickup_details(
    pickup_id: str, user: CurrentUser = Depends(resident_only), store: DataStore = Depends(get_store)
) -> residents.PickupDetails:
    return residents.pickup_details(store, user.uid, pickup_id)


@router.get("/households/me/consent", response_model=residents.ConsentView)
def get_consent(
    user: CurrentUser = Depends(resident_only), store: DataStore = Depends(get_store)
) -> residents.ConsentView:
    return residents.consent_view(store, services.get_household(store, user.uid))


@router.put("/households/me/consent", response_model=residents.ConsentView)
def put_consent(
    body: ConsentRequest,
    user: CurrentUser = Depends(resident_only),
    store: DataStore = Depends(get_store),
    clock: Clock = Depends(get_clock),
) -> residents.ConsentView:
    household = services.get_household(store, user.uid)
    updated = residents.set_consent(store, clock, household, body.dataSharing, by=user.uid)
    return residents.consent_view(store, updated)


class ClickResponse(BaseModel):
    url: str


@router.get("/residents/me/swaps", response_model=recommendations.SwapsResponse)
async def swaps(
    user: CurrentUser = Depends(resident_only),
    store: DataStore = Depends(get_store),
    ranker: Ranker = Depends(get_ranker),
    limiter: RateLimiter = Depends(get_tips_limiter),
    clock: Clock = Depends(get_clock),
) -> recommendations.SwapsResponse:
    """Personal sustainable swaps (requires data-sharing consent; 403 consent_required otherwise)."""
    return await run_in_threadpool(recommendations.get_swaps, store, ranker, limiter, clock, user.uid)


@router.post("/residents/me/swaps/{sku}/click", response_model=ClickResponse)
def swap_click(
    sku: str,
    user: CurrentUser = Depends(resident_only),
    store: DataStore = Depends(get_store),
    clock: Clock = Depends(get_clock),
) -> ClickResponse:
    """Count an anonymous click (partner + product + day) and return the product URL."""
    return ClickResponse(url=recommendations.record_click(store, clock, user.uid, sku))
