"""Admin dashboard services: overview, AI quality, pickups, people, partners.

Cost: pickup/user counts use Firestore count() aggregations; per-zone/category
numbers read the small per-household stats docs once; read endpoints are
cached for 60 s in memory (cleared by admin writes).
"""

import math
import re
import threading
import time
from collections import defaultdict
from collections.abc import Callable
from datetime import datetime, timedelta
from typing import Any

from pydantic import BaseModel, Field

from app.clock import Clock, local_today
from app.demo import DEMO_UIDS
from app.errors import DomainError
from app.identity import IdentityAdmin
from app.models import (
    BagStatus,
    Household,
    Partner,
    PickupStatus,
    Role,
    UserProfile,
    WasteRecord,
)

from app.partner_api import generate_key
from app.secrets import DEMO_PARTNER_IDS
from app.services import attached_bags, route_stop
from app.store import DataStore
from app.taxonomy import CATEGORIES
from app.transitions import advance_pickup, reassign_pickup
from app.users import UserStore
from app.zones import ZONE_IDS

CACHE_TTL_S = 60.0
LOW_CONFIDENCE = 0.6  # same threshold the operator UI highlights
SCANNED = {BagStatus.COLLECTED, BagStatus.AT_WAREHOUSE, BagStatus.PROCESSED}


class TTLCache:
    """Tiny per-instance cache for admin read endpoints."""

    def __init__(self, ttl_s: float = CACHE_TTL_S, clock: Callable[[], float] = time.monotonic) -> None:
        self.ttl = ttl_s
        self._clock = clock
        self._data: dict[tuple, tuple[float, Any]] = {}
        self._lock = threading.Lock()

    def get_or_set(self, key: tuple, factory: Callable[[], Any]) -> Any:  # noqa: ANN401
        now = self._clock()
        with self._lock:
            hit = self._data.get(key)
            if hit and hit[0] > now:
                return hit[1]
        value = factory()
        with self._lock:
            self._data[key] = (now + self.ttl, value)
        return value

    def clear(self) -> None:
        with self._lock:
            self._data.clear()


def is_demo_household(household: Household | None) -> bool:
    return household is not None and (household.isSynthetic or household.id in DEMO_UIDS)


# --- overview ---


class ZoneRow(BaseModel):
    zone: str
    households: int
    bags: int
    quantity: int
    recyclableShare: float | None
    topCategory: str | None
    avgEcoScore: float | None


class Overview(BaseModel):
    range: str
    dateFrom: str
    dateTo: str
    includeSynthetic: bool
    syntheticHouseholds: int
    pickupsToday: dict[str, int]
    pickupsInRange: dict[str, int]
    pickupsUpcoming: dict[str, int] = Field(description="Scheduled for the next 14 days (after today).")
    bagsProcessed: int = Field(description="All time, from household stats.")
    activeHouseholds: int = Field(description="Households with at least one processed bag.")
    collectors: int
    categories: dict[str, int]
    totalQuantity: int
    recyclableShare: float | None
    zones: list[ZoneRow]
    generatedAt: datetime


UPCOMING_DAYS = 14


def overview(store: DataStore, users: UserStore, clock: Clock, days: int, include_synthetic: bool) -> Overview:
    today = local_today(clock)
    start = today - timedelta(days=days - 1)

    def counts(date_from: str, date_to: str) -> dict[str, int]:
        out = {}
        for status in PickupStatus:
            n = store.count_pickups(status, date_from, date_to)
            if not include_synthetic:
                n -= store.count_pickups(status, date_from, date_to, synthetic_only=True)
            out[status.value] = n
        return out

    rows = store.list_all_stats()
    synthetic_households = sum(1 for _, s in rows if s.isSynthetic)
    categories: dict[str, int] = {c: 0 for c in CATEGORIES}
    recyclable = bags = active = 0
    by_zone: dict[str, dict[str, Any]] = defaultdict(lambda: {"h": 0, "bags": 0, "q": 0, "rec": 0, "cats": defaultdict(int), "scores": []})
    for _, s in rows:
        if not include_synthetic and s.isSynthetic:
            continue
        if include_synthetic:
            cats = {c: v.quantity for c, v in s.categories.items()}
            h_bags, h_rec = s.bagsProcessed, s.recyclableQuantity
        else:
            real = s.realOnly or {}
            cats = dict(real.get("categories", {}))
            h_bags, h_rec = int(real.get("bags", 0)), int(real.get("recyclableQuantity", 0))
        if h_bags == 0:
            continue
        active += 1
        bags += h_bags
        recyclable += h_rec
        zone = by_zone[s.zone or "unknown"]
        zone["h"] += 1
        zone["bags"] += h_bags
        zone["rec"] += h_rec
        if s.ecoScore is not None:
            zone["scores"].append(s.ecoScore)
        for c, q in cats.items():
            categories[c] = categories.get(c, 0) + q
            zone["q"] += q
            zone["cats"][c] += q
    total = sum(categories.values())
    zones = [
        ZoneRow(
            zone=z, households=v["h"], bags=v["bags"], quantity=v["q"],
            recyclableShare=round(v["rec"] / v["q"], 3) if v["q"] else None,
            topCategory=max(v["cats"], key=v["cats"].get) if v["cats"] else None,
            avgEcoScore=round(sum(v["scores"]) / len(v["scores"]), 1) if v["scores"] else None,
        )
        for z, v in sorted(by_zone.items())
    ]
    return Overview(
        range=f"{days}d", dateFrom=start.isoformat(), dateTo=today.isoformat(), includeSynthetic=include_synthetic,
        syntheticHouseholds=synthetic_households,
        pickupsToday=counts(today.isoformat(), today.isoformat()),
        pickupsInRange=counts(start.isoformat(), today.isoformat()),
        pickupsUpcoming=counts((today + timedelta(days=1)).isoformat(), (today + timedelta(days=UPCOMING_DAYS)).isoformat()),
        bagsProcessed=bags, activeHouseholds=active, collectors=users.count_by_role(Role.COLLECTOR),
        categories=categories, totalQuantity=total,
        recyclableShare=round(recyclable / total, 3) if total else None,
        zones=zones, generatedAt=clock.now(),
    )


# --- AI quality ---


class AiQuality(BaseModel):
    recordsConsidered: int = Field(description="Real (non-synthetic) bags confirmed by operators.")
    bagsAnalyzed: int = Field(description="Confirmed bags that have a Gemini result.")
    correctionRate: float | None = Field(description="Share of analyzed bags the operator changed (0-1).")
    avgCorrectionsPerBag: float | None
    avgLatencyMs: float | None
    p95LatencyMs: int | None
    failures: int = Field(description="Gemini calls that failed (timeout/5xx/invalid output).")
    manualFallbacks: int = Field(description="Bags confirmed by manual entry (no AI result).")
    lowConfidenceShare: float | None = Field(description="Share of AI items below 0.6 confidence.")
    itemsAdded: int
    itemsRemoved: int
    itemsModified: int
    estimatedEditRecords: int = Field(description="Older records whose add/remove split is estimated.")
    models: dict[str, int]


def p95(values: list[int]) -> int | None:
    """Nearest-rank 95th percentile."""
    if not values:
        return None
    ordered = sorted(values)
    return ordered[max(0, math.ceil(0.95 * len(ordered)) - 1)]


def ai_quality(records: list[WasteRecord], drafts: list[WasteRecord]) -> AiQuality:
    real = [r for r in records if not r.isSynthetic and not r.isTest]
    drafts = [d for d in drafts if not d.isTest]
    analyzed = [r for r in real if r.aiResult is not None]
    latencies = [r.latencyMs for r in analyzed if r.latencyMs is not None]
    ai_items = [i for r in analyzed for i in r.aiResult.items]  # type: ignore[union-attr]
    added = removed = modified = estimated = 0
    for r in analyzed:
        if r.itemsAdded is not None:
            added += r.itemsAdded
            removed += r.itemsRemoved or 0
            modified += r.itemsModified or 0
        else:
            estimated += 1
            diff = len(r.finalItems) - len(r.aiResult.items)  # type: ignore[union-attr]
            added += max(0, diff)
            removed += max(0, -diff)
    models: dict[str, int] = defaultdict(int)
    for r in analyzed:
        models[r.model or "unknown"] += 1
    failures = sum(1 for r in real if r.aiError) + sum(1 for d in drafts if d.aiError and not d.isSynthetic)
    return AiQuality(
        recordsConsidered=len(real),
        bagsAnalyzed=len(analyzed),
        correctionRate=round(sum(1 for r in analyzed if r.edited) / len(analyzed), 3) if analyzed else None,
        avgCorrectionsPerBag=round(sum(r.editCount for r in analyzed) / len(analyzed), 2) if analyzed else None,
        avgLatencyMs=round(sum(latencies) / len(latencies), 1) if latencies else None,
        p95LatencyMs=p95(latencies),
        failures=failures,
        manualFallbacks=sum(1 for r in real if r.source == "manual"),
        lowConfidenceShare=round(sum(1 for i in ai_items if i.confidence < LOW_CONFIDENCE) / len(ai_items), 3)
        if ai_items else None,
        itemsAdded=added, itemsRemoved=removed, itemsModified=modified, estimatedEditRecords=estimated,
        models=dict(models),
    )


# --- pickups ---


class PickupRow(BaseModel):
    id: str
    date: str
    timeSlot: str
    status: str
    zone: str
    householdName: str
    bagCount: int
    collectorUid: str | None
    collectorName: str | None
    isDemo: bool


class PickupPage(BaseModel):
    items: list[PickupRow]
    page: int
    pageSize: int
    total: int


class TimelineEvent(BaseModel):
    at: datetime
    kind: str  # pickup | bag
    status: str
    by: str
    bagCode: str | None = None


class PickupDetail(BaseModel):
    pickup: PickupRow
    addressLine: str
    notes: str
    bags: list[dict]
    timeline: list[TimelineEvent]
    canReassign: bool


def _collector_names(users: UserStore, uids: set[str]) -> dict[str, str]:
    out = {}
    for uid in uids:
        profile = users.get(uid)
        out[uid] = profile.name if profile else uid
    return out


def _row(pickup, household: Household | None, names: dict[str, str]) -> PickupRow:  # noqa: ANN001
    return PickupRow(
        id=pickup.id, date=pickup.date, timeSlot=pickup.timeSlot, status=pickup.status, zone=pickup.zone,
        householdName=household.name if household else pickup.householdId, bagCount=len(pickup.bagCodes),
        collectorUid=pickup.collectorUid, collectorName=names.get(pickup.collectorUid or ""),
        isDemo=is_demo_household(household),
    )


def list_pickups(store: DataStore, users: UserStore, day: str, zone: str | None, status: str | None,
                 page: int, page_size: int) -> PickupPage:
    if zone is not None and zone not in ZONE_IDS:
        raise DomainError(422, "invalid_zone")
    pickups = sorted(store.list_pickups_by_date(day, zone, status), key=lambda p: (p.timeSlot != "morning", p.createdAt))
    households = store.get_households([p.householdId for p in pickups])
    names = _collector_names(users, {p.collectorUid for p in pickups if p.collectorUid})
    start = (page - 1) * page_size
    items = [_row(p, households.get(p.householdId), names) for p in pickups[start:start + page_size]]
    return PickupPage(items=items, page=page, pageSize=page_size, total=len(pickups))


def pickup_detail(store: DataStore, users: UserStore, pickup_id: str) -> PickupDetail:
    pickup = store.get_pickup(pickup_id)
    if pickup is None:
        raise DomainError(404, "pickup_not_found")
    household = store.get_household(pickup.householdId)
    names = _collector_names(users, {pickup.collectorUid} if pickup.collectorUid else set())
    bags = store.get_bags(pickup.bagCodes)
    events = [TimelineEvent(at=e.at, kind="pickup", status=e.status, by=e.by) for e in pickup.statusHistory]
    for code, bag in bags.items():
        events += [TimelineEvent(at=e.at, kind="bag", status=e.status, by=e.by, bagCode=code)
                   for e in bag.statusHistory if e.at >= pickup.createdAt]
    any_scanned = any(b.status in SCANNED for b in attached_bags(store, pickup))
    return PickupDetail(
        pickup=_row(pickup, household, names),
        addressLine=household.addressLine if household else "",
        notes=pickup.notes,
        bags=[{"code": c, "status": b.status, "attached": b.pickupId == pickup.id} for c, b in bags.items()],
        timeline=sorted(events, key=lambda e: e.at),
        canReassign=pickup.status == PickupStatus.REQUESTED or (pickup.status == PickupStatus.ASSIGNED and not any_scanned),
    )


def assign_pickup(store: DataStore, users: UserStore, clock: Clock, admin_uid: str, pickup_id: str,
                  collector_uid: str, demo_admin: bool) -> PickupDetail:
    pickup = store.get_pickup(pickup_id)
    if pickup is None:
        raise DomainError(404, "pickup_not_found")
    household = store.get_household(pickup.householdId)
    if demo_admin and not is_demo_household(household):
        raise DomainError(403, "demo_disabled")
    collector = users.get(collector_uid)
    if collector is None or collector.role != Role.COLLECTOR:
        raise DomainError(422, "not_a_collector")
    if pickup.zone not in collector.zones:
        raise DomainError(409, "outside_collector_zones")
    if pickup.status == PickupStatus.REQUESTED:
        updated = advance_pickup(pickup, PickupStatus.ASSIGNED, by=admin_uid, clock=clock,
                                 collectorUid=collector_uid, assignedAt=clock.now())
    else:
        if pickup.collectorUid == collector_uid:
            raise DomainError(409, "already_assigned")
        bags = attached_bags(store, pickup)
        updated = reassign_pickup(pickup, collector_uid, by=admin_uid, clock=clock,
                                  any_scanned=any(b.status in SCANNED for b in bags))
    # The route mirror (doc id = pickup id) moves to the new collector in the same batch.
    store.commit([updated], [], [route_stop(updated, household, attached_bags(store, updated), clock)])
    return pickup_detail(store, users, pickup_id)


# --- people ---


def mask_email(email: str | None) -> str | None:
    if not email or "@" not in email:
        return email
    local, domain = email.split("@", 1)
    return f"{local[:1]}•••@{domain}"


def list_users(users: UserStore, role: Role | None, mask_real_emails: bool = False) -> list[UserProfile]:
    """All accounts by role. The public demo admin sees real users' emails masked."""
    roles = [role] if role else list(Role)
    found = sorted((u for r in roles for u in users.list_by_role(r)), key=lambda u: (u.role, u.name))
    if not mask_real_emails:
        return found
    return [u if u.isSynthetic or u.uid in DEMO_UIDS else u.model_copy(update={"email": mask_email(u.email)})
            for u in found]


class StaffCreated(BaseModel):
    uid: str
    setupLink: str = Field(description="One-time password setup link (shown once).")


def create_staff(identity: IdentityAdmin, users: UserStore, email: str, name: str, role: Role,
                 zones: list[str]) -> StaffCreated:
    if role not in (Role.COLLECTOR, Role.OPERATOR):
        raise DomainError(422, "invalid_staff_role")
    if any(z not in ZONE_IDS for z in zones) or (role == Role.COLLECTOR and not zones):
        raise DomainError(422, "invalid_zones")
    uid, link = identity.create_staff_user(email.strip().lower(), name.strip())
    identity.set_role(uid, role)
    users.upsert(uid, name.strip(), email.strip().lower(), role)
    if role == Role.COLLECTOR:
        users.set_zones(uid, zones)
    return StaffCreated(uid=uid, setupLink=link)


def set_collector_zones(users: UserStore, uid: str, zones: list[str]) -> UserProfile:
    profile = users.get(uid)
    if profile is None or profile.role != Role.COLLECTOR:
        raise DomainError(404, "collector_not_found")
    if not zones or any(z not in ZONE_IDS for z in zones):
        raise DomainError(422, "invalid_zones")
    users.set_zones(uid, zones)
    return profile.model_copy(update={"zones": zones})


# --- partners ---


class ProductStat(BaseModel):
    sku: str
    name: str
    impressions: int
    clicks: int


class PartnerRow(BaseModel):
    id: str
    name: str
    active: bool
    isDemo: bool
    keyPrefix: str
    catalogSize: int
    impressions: int
    clicks: int
    ctr: float | None
    topProducts: list[ProductStat]


class PartnerKey(BaseModel):
    partner: PartnerRow
    apiKey: str = Field(description="Shown once. Only its SHA-256 hash is stored.")


def _partner_row(store: DataStore, partner: Partner, since_day: str) -> PartnerRow:
    catalog = {i.sku: i.name for i in store.list_catalog(partner.id)}
    impressions: dict[str, int] = defaultdict(int)
    clicks: dict[str, int] = defaultdict(int)
    for day in store.list_partner_metrics(partner.id, since_day):
        for sku, n in (day.get("impressions") or {}).items():
            impressions[sku] += int(n)
        for sku, n in (day.get("clicks") or {}).items():
            clicks[sku] += int(n)
    skus = set(impressions) | set(clicks)
    top = sorted(skus, key=lambda s: (-clicks[s], -impressions[s], s))[:3]
    total_i, total_c = sum(impressions.values()), sum(clicks.values())
    return PartnerRow(
        id=partner.id, name=partner.name, active=partner.active, isDemo=partner.id in DEMO_PARTNER_IDS,
        keyPrefix=partner.keyPrefix, catalogSize=len(catalog), impressions=total_i, clicks=total_c,
        ctr=round(total_c / total_i, 3) if total_i else None,
        topProducts=[ProductStat(sku=s, name=catalog.get(s, s), impressions=impressions[s], clicks=clicks[s]) for s in top],
    )


def list_partners(store: DataStore, clock: Clock, days: int = 30) -> list[PartnerRow]:
    since = (local_today(clock) - timedelta(days=days - 1)).isoformat()
    return [_partner_row(store, p, since) for p in sorted(store.list_partners(), key=lambda p: p.name)]


def _slug(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")[:40]


def create_partner(store: DataStore, clock: Clock, name: str) -> PartnerKey:
    partner_id = _slug(name)
    if not partner_id:
        raise DomainError(422, "invalid_name")
    if store.get_partner(partner_id) is not None:
        raise DomainError(409, "partner_exists")
    key, key_hash, prefix = generate_key(partner_id)
    partner = Partner(id=partner_id, name=name.strip(), apiKeyHash=key_hash, keyPrefix=prefix, active=True,
                      createdAt=clock.now())
    store.save_partner(partner, [])
    return PartnerKey(partner=_partner_row(store, partner, local_today(clock).isoformat()), apiKey=key)


def rotate_partner_key(store: DataStore, clock: Clock, partner_id: str) -> PartnerKey:
    partner = store.get_partner(partner_id)
    if partner is None:
        raise DomainError(404, "partner_not_found")
    if partner_id in DEMO_PARTNER_IDS:
        # Its plain key lives in Secret Manager; rotating here would desync it. Use the seed script.
        raise DomainError(409, "demo_partner_key_managed_by_seed")
    key, key_hash, prefix = generate_key(partner_id)
    updated = partner.model_copy(update={"apiKeyHash": key_hash, "keyPrefix": prefix})
    store.save_partner(updated, [])
    return PartnerKey(partner=_partner_row(store, updated, local_today(clock).isoformat()), apiKey=key)

