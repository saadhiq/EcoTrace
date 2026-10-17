"""Partner API logic: API keys, anonymised segments, segment recommendations, zone insights.

Privacy: only households that CONSENTED to data sharing are counted, partners
never receive household-level data, and every reported group (segment, or
zone x month cell) must contain at least K_MIN households or it is suppressed.
"""

import hashlib
import hmac
import secrets
from collections import defaultdict

from pydantic import BaseModel, Field

from app.errors import DomainError
from app.models import CatalogItem, Household, HouseholdStats, Partner
from app.recommendations import find_candidates
from app.segments import SEGMENTS, SEGMENTS_BY_NAME
from app.store import DataStore
from app.taxonomy import CATEGORY_LABELS
from app.zones import ZONE_IDS

K_MIN = 5
KEY_PREFIX = "etp"


# --- API keys: "etp.<partnerId>.<random>"; only a SHA-256 hash is stored ---


def hash_key(key: str) -> str:
    return hashlib.sha256(key.encode()).hexdigest()


def generate_key(partner_id: str) -> tuple[str, str, str]:
    """(key, sha256 hash, display prefix). Show the key once; store only the hash."""
    key = f"{KEY_PREFIX}.{partner_id}.{secrets.token_urlsafe(32)}"
    return key, hash_key(key), key[: len(KEY_PREFIX) + len(partner_id) + 6]


def verify_key(store: DataStore, key: str | None) -> Partner:
    parts = (key or "").split(".")
    if len(parts) != 3 or parts[0] != KEY_PREFIX:
        raise DomainError(401, "invalid_api_key")
    partner = store.get_partner(parts[1])
    if partner is None or not partner.active or not hmac.compare_digest(partner.apiKeyHash, hash_key(key or "")):
        raise DomainError(401, "invalid_api_key")
    return partner


# --- response models (with examples for the OpenAPI docs) ---


class Share(BaseModel):
    name: str
    share: float = Field(description="Share of the segment's waste quantity (0-1).")


class ItemType(BaseModel):
    itemType: str
    avgPerHousehold: float


class SegmentSummary(BaseModel):
    name: str
    title: str
    description: str
    households: int = Field(description=f"Consenting households in the segment (always >= {K_MIN}).")
    topCategories: list[Share]
    topItemTypes: list[ItemType]

    model_config = {"json_schema_extra": {"examples": [{
        "name": "beverage-plastic-heavy", "title": "Beverage-plastic heavy",
        "description": "Plastic + metal are at least 45% of their waste and drink containers at least 25%.",
        "households": 7,
        "topCategories": [{"name": "plastic", "share": 0.48}, {"name": "metal", "share": 0.21}],
        "topItemTypes": [{"itemType": "drink bottle", "avgPerHousehold": 9.4}],
    }]}}


class SegmentsResponse(BaseModel):
    kThreshold: int = K_MIN
    consentingHouseholds: int = Field(description="Total consenting households considered (before suppression).")
    segments: list[SegmentSummary]
    suppressedSegments: int = Field(description=f"Segments hidden because they have fewer than {K_MIN} households.")


class PartnerRecommendation(BaseModel):
    sku: str
    name: str
    category: str
    ecoBenefit: str
    price: float
    url: str
    reason: str = Field(description="Segment-level reason (never about an individual household).")


class SegmentRecommendations(BaseModel):
    segment: str
    households: int
    recommendations: list[PartnerRecommendation]

    model_config = {"json_schema_extra": {"examples": [{
        "segment": "beverage-plastic-heavy", "households": 7,
        "recommendations": [{
            "sku": "GC-001", "name": "Stainless steel water bottle (750 ml)", "category": "plastic",
            "ecoBenefit": "Replaces ~150 single-use bottles a year", "price": 2450.0,
            "url": "https://greencart.example/p/GC-001",
            "reason": "Households in this segment disposed of 9.4 drink bottles each on average.",
        }],
    }]}}


class MonthCell(BaseModel):
    month: str
    households: int
    categories: dict[str, int]


class ZoneInsights(BaseModel):
    zone: str
    households: int | None = Field(description=f"Consenting households (null if fewer than {K_MIN}).")
    suppressed: bool
    months: list[MonthCell]


class InsightsResponse(BaseModel):
    kThreshold: int = K_MIN
    zones: list[ZoneInsights]

    model_config = {"json_schema_extra": {"examples": [{
        "kThreshold": 5,
        "zones": [{"zone": "colombo-07", "households": 8, "suppressed": False, "months": [
            {"month": "2026-09", "households": 6, "categories": {"plastic": 41, "paper_cardboard": 23}}]}],
    }]}}


# --- aggregation over consenting households ---


def _consenting(store: DataStore) -> list[tuple[Household, HouseholdStats]]:
    households = store.list_consenting_households()
    stats = store.get_stats_many([h.id for h in households])
    return [(h, stats[h.id]) for h in households if h.id in stats and stats[h.id].bagsProcessed > 0]


def _group_by_segment(rows: list[tuple[Household, HouseholdStats]]) -> dict[str, list[HouseholdStats]]:
    groups: dict[str, list[HouseholdStats]] = defaultdict(list)
    for _, s in rows:
        if s.segment:
            groups[s.segment].append(s)
    return groups


def _segment_summary(name: str, members: list[HouseholdStats]) -> SegmentSummary:
    category_qty: dict[str, int] = defaultdict(int)
    type_qty: dict[str, int] = defaultdict(int)
    for s in members:
        for c, stat in s.categories.items():
            category_qty[c] += stat.quantity
        for t, q in s.productTypes.items():
            type_qty[t] += q
    total = sum(category_qty.values()) or 1
    seg = SEGMENTS_BY_NAME[name]
    return SegmentSummary(
        name=name, title=seg.title, description=seg.description, households=len(members),
        topCategories=[Share(name=c, share=round(q / total, 3))
                       for c, q in sorted(category_qty.items(), key=lambda kv: -kv[1])[:3] if q],
        topItemTypes=[ItemType(itemType=t, avgPerHousehold=round(q / len(members), 1))
                      for t, q in sorted(type_qty.items(), key=lambda kv: (-kv[1], kv[0]))[:5]],
    )


def segments(store: DataStore) -> SegmentsResponse:
    rows = _consenting(store)
    groups = _group_by_segment(rows)
    order = [s.name for s in SEGMENTS]
    visible = [_segment_summary(n, groups[n]) for n in order if len(groups.get(n, [])) >= K_MIN]
    return SegmentsResponse(
        consentingHouseholds=len(rows),
        segments=visible,
        suppressedSegments=sum(1 for n in order if 0 < len(groups.get(n, [])) < K_MIN),
    )


def segment_recommendations(store: DataStore, partner: Partner, name: str, limit: int = 5) -> SegmentRecommendations:
    groups = _group_by_segment(_consenting(store))
    members = groups.get(name, [])
    if name not in SEGMENTS_BY_NAME or len(members) < K_MIN:
        raise DomainError(404, "segment_not_available")
    type_qty: dict[str, int] = defaultdict(int)
    category_qty: dict[str, int] = defaultdict(int)
    for s in members:
        for t, q in s.productTypes.items():
            type_qty[t] += q
        for c, stat in s.categories.items():
            category_qty[c] += stat.quantity
    catalog: list[CatalogItem] = store.list_catalog(partner.id)
    candidates = find_candidates(dict(type_qty), dict(category_qty), [(partner, catalog)], limit=limit)
    n = len(members)
    recs = []
    for c in candidates:
        if c.matched:
            item_type, qty = c.matched[0]
            reason = f"Households in this segment disposed of {qty / n:.1f} {item_type}s each on average."
        else:
            cat = c.category_match or c.item.category
            share = category_qty.get(cat, 0) / (sum(category_qty.values()) or 1)
            reason = f"{CATEGORY_LABELS.get(cat, cat)} is {share:.0%} of this segment's waste."
        recs.append(PartnerRecommendation(
            sku=c.item.sku, name=c.item.name, category=c.item.category, ecoBenefit=c.item.ecoBenefit,
            price=c.item.price, url=c.item.url, reason=reason,
        ))
    return SegmentRecommendations(segment=name, households=n, recommendations=recs)


def zone_insights(store: DataStore, zone: str | None) -> InsightsResponse:
    if zone is not None and zone not in ZONE_IDS:
        raise DomainError(422, "invalid_zone")
    by_zone: dict[str, list[HouseholdStats]] = defaultdict(list)
    for household, s in _consenting(store):
        by_zone[household.zone].append(s)
    zones = [zone] if zone else sorted(ZONE_IDS)
    out = []
    for z in zones:
        members = by_zone.get(z, [])
        if len(members) < K_MIN:
            out.append(ZoneInsights(zone=z, households=None, suppressed=True, months=[]))
            continue
        cells: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
        contributors: dict[str, int] = defaultdict(int)
        for s in members:
            for month, cats in s.monthly.items():
                contributors[month] += 1
                for c, q in cats.items():
                    cells[month][c] += q
        months = [
            MonthCell(month=m, households=contributors[m], categories=dict(sorted(cells[m].items())))
            for m in sorted(cells) if contributors[m] >= K_MIN  # K applies to every reported cell
        ]
        out.append(ZoneInsights(zone=z, households=len(members), suppressed=False, months=months))
    return InsightsResponse(zones=out)
