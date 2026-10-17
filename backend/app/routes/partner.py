"""Partner API v1 (server-to-server, X-API-Key)."""

import logging

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Security, status
from fastapi.security import APIKeyHeader

from app import partner_api
from app.deps import get_store
from app.models import Partner
from app.ratelimit import RateLimiter
from app.store import DataStore

logger = logging.getLogger(__name__)

TAG = "Partner API v1"
TAG_DESCRIPTION = f"""
Anonymised, consent-based data for recycling and sustainable-product partners.

* **Auth:** send your key in the `X-API-Key` header (click **Authorize** above to try it here).
* **Privacy:** only households that **opted in** to data sharing are counted; you never receive
  household-level data; any segment or zone-month with fewer than **{partner_api.K_MIN} households is suppressed**.
* **Limits:** 60 requests per minute per key (HTTP 429 with `Retry-After` when exceeded).
* Errors: `401 invalid_api_key`, `404 segment_not_available`, `422 invalid_zone`, `429 rate_limited`.
"""

router = APIRouter(prefix="/partner/v1", tags=[TAG])
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False, description="Your partner API key.")


def get_partner_limiter(request: Request) -> RateLimiter:
    return request.app.state.partner_limiter


def current_partner(
    request: Request,
    key: str | None = Security(api_key_header),
    store: DataStore = Depends(get_store),
    limiter: RateLimiter = Depends(get_partner_limiter),
) -> Partner:
    partner = partner_api.verify_key(store, key)
    if not limiter.allow(partner.id):
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, detail="rate_limited", headers={"Retry-After": "60"})
    # Usage log (partner + endpoint only; no household data involved).
    logger.info("partner_api partner=%s method=%s path=%s", partner.id, request.method, request.url.path)
    return partner


@router.get(
    "/segments",
    response_model=partner_api.SegmentsResponse,
    summary="Anonymised household segments",
    description="Rule-based segments of consenting households with size, top waste categories and item types. "
    f"Segments with fewer than {partner_api.K_MIN} households are suppressed.",
)
def segments(_: Partner = Depends(current_partner), store: DataStore = Depends(get_store)) -> partner_api.SegmentsResponse:
    return partner_api.segments(store)


@router.get(
    "/segments/{name}/recommendations",
    response_model=partner_api.SegmentRecommendations,
    summary="Your products that fit a segment",
    description="Which of YOUR catalog items replace what this segment throws away, with segment-level reasons.",
)
def segment_recommendations(
    name: str,
    partner: Partner = Depends(current_partner),
    store: DataStore = Depends(get_store),
) -> partner_api.SegmentRecommendations:
    return partner_api.segment_recommendations(store, partner, name)


@router.get(
    "/insights",
    response_model=partner_api.InsightsResponse,
    summary="Category trends by zone",
    description="Monthly waste quantities per category by zone (consenting households only). A zone or month "
    f"with fewer than {partner_api.K_MIN} contributing households is suppressed.",
)
def insights(
    zone: str | None = Query(default=None, description="Zone id, e.g. colombo-07. Omit for all zones.",
                             examples=["colombo-07"]),
    _: Partner = Depends(current_partner),
    store: DataStore = Depends(get_store),
) -> partner_api.InsightsResponse:
    return partner_api.zone_insights(store, zone)
