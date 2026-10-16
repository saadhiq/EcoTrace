"""Collector flow: accept pickups, scan bags at the door, hand over at the warehouse.

Same write pattern as the resident flow: validate, then one atomic batch
(pickup + bags + route mirror). Status changes go through app.transitions.
"""

from pydantic import BaseModel

from app.bagcodes import is_valid_code
from app.clock import Clock
from app.errors import DomainError
from app.models import Bag, BagStatus, Household, Pickup, PickupStatus, TimeSlot
from app.services import attached_bags, release_bags, route_stop
from app.store import DataStore
from app.transitions import advance_bag, advance_pickup

SCANNED = {BagStatus.COLLECTED, BagStatus.AT_WAREHOUSE, BagStatus.PROCESSED}
SLOT_ORDER = {TimeSlot.MORNING: 0, TimeSlot.AFTERNOON: 1}
# After collection, only bags that stayed attached count; before (and for
# missed/cancelled pickups) the expected count is every bag listed.
_COLLECTED_STATES = {PickupStatus.COLLECTED, PickupStatus.DELIVERED, PickupStatus.PROCESSED}
MAX_REASON = 280


# --- views (what the API returns; never bag codes before they're scanned) ---


class CollectorPickup(BaseModel):
    id: str
    date: str
    timeSlot: TimeSlot
    status: PickupStatus
    zone: str
    householdName: str
    addressLine: str
    phone: str
    notes: str
    bagCount: int
    scannedCount: int
    mine: bool
    missedReason: str | None = None
    missingBagsReason: str | None = None


class BagSlot(BaseModel):
    slot: int  # 1-based position in the pickup
    status: str  # bag status, or "released" if it went back to the resident
    code: str | None  # only once scanned


class CollectorPickupDetail(CollectorPickup):
    slots: list[BagSlot]


class ScanResult(BaseModel):
    code: str
    slot: int
    alreadyScanned: bool
    pickup: CollectorPickupDetail


class HandoverPickup(BaseModel):
    pickupId: str
    date: str
    householdName: str
    bags: list[BagSlot]  # codes included: all of these were scanned


class HandoverScanResult(BaseModel):
    code: str
    alreadyScanned: bool
    pickupId: str
    pickupDelivered: bool


def _summary(pickup: Pickup, household: Household | None, bags: list[Bag], uid: str) -> dict:
    return {
        "id": pickup.id,
        "date": pickup.date,
        "timeSlot": pickup.timeSlot,
        "status": pickup.status,
        "zone": pickup.zone,
        "householdName": household.name if household else "Household",
        "addressLine": household.addressLine if household else "",
        "phone": household.phone if household else "",
        "notes": pickup.notes,
        "bagCount": len(bags) if pickup.status in _COLLECTED_STATES else len(pickup.bagCodes),
        "scannedCount": sum(1 for b in bags if b.status in SCANNED),
        "mine": pickup.collectorUid == uid,
        "missedReason": pickup.missedReason,
        "missingBagsReason": pickup.missingBagsReason,
    }


def _detail(store: DataStore, pickup: Pickup, uid: str) -> CollectorPickupDetail:
    household = store.get_household(pickup.householdId)
    all_bags = store.get_bags(pickup.bagCodes)
    attached = [b for b in all_bags.values() if b.pickupId == pickup.id]
    slots = []
    for i, code in enumerate(pickup.bagCodes, start=1):
        bag = all_bags.get(code)
        if bag is None or bag.pickupId != pickup.id:
            slots.append(BagSlot(slot=i, status="released", code=None))
        else:
            slots.append(
                BagSlot(slot=i, status=bag.status, code=code if bag.status in SCANNED else None)
            )
    return CollectorPickupDetail(**_summary(pickup, household, attached, uid), slots=slots)


# --- reads ---


def list_day(
    store: DataStore, uid: str, zones: list[str], day: str
) -> tuple[list[CollectorPickup], list[CollectorPickup]]:
    """(available in my zones, my route) for one date, morning first."""
    available = store.list_requested_pickups(zones, day)
    mine = store.list_collector_pickups(uid, day=day)
    households = store.get_households([p.householdId for p in available + mine])

    def view(p: Pickup, with_bags: bool) -> CollectorPickup:
        bags = attached_bags(store, p) if with_bags else []
        return CollectorPickup(**_summary(p, households.get(p.householdId), bags, uid))

    def order(items: list[Pickup]) -> list[Pickup]:
        return sorted(items, key=lambda p: (SLOT_ORDER[p.timeSlot], p.createdAt))

    return (
        [view(p, False) for p in order(available)],
        [view(p, True) for p in order(mine)],
    )


def _visible_pickup(store: DataStore, uid: str, zones: list[str], pickup_id: str) -> Pickup:
    pickup = store.get_pickup(pickup_id)
    visible = pickup is not None and (
        pickup.collectorUid == uid
        or (pickup.status == PickupStatus.REQUESTED and pickup.zone in zones)
    )
    if not visible:
        raise DomainError(404, "pickup_not_found")
    assert pickup is not None
    return pickup


def get_pickup(store: DataStore, uid: str, zones: list[str], pickup_id: str) -> CollectorPickupDetail:
    return _detail(store, _visible_pickup(store, uid, zones, pickup_id), uid)


def _my_active_pickup(store: DataStore, uid: str, pickup_id: str) -> Pickup:
    pickup = store.get_pickup(pickup_id)
    if pickup is None or pickup.collectorUid != uid:
        raise DomainError(404, "pickup_not_found")
    if pickup.status != PickupStatus.ASSIGNED:
        raise DomainError(409, "pickup_not_active")
    return pickup


def _commit(store: DataStore, clock: Clock, pickup: Pickup, bags: list[Bag]) -> None:
    """Write pickup + changed bags + the refreshed route mirror in one batch."""
    by_code = {b.code: b for b in attached_bags(store, pickup)}
    for bag in bags:
        if bag.pickupId == pickup.id:
            by_code[bag.code] = bag
        else:
            by_code.pop(bag.code, None)
    household = store.get_household(pickup.householdId)
    store.commit([pickup], bags, [route_stop(pickup, household, list(by_code.values()), clock)])


# --- actions ---


def accept(store: DataStore, clock: Clock, uid: str, zones: list[str], pickup_id: str) -> CollectorPickupDetail:
    pickup = store.get_pickup(pickup_id)
    if pickup is None:
        raise DomainError(404, "pickup_not_found")
    if pickup.collectorUid == uid and pickup.status == PickupStatus.ASSIGNED:
        return _detail(store, pickup, uid)  # already mine: idempotent
    if pickup.status != PickupStatus.REQUESTED:
        raise DomainError(409, "pickup_not_available")
    if pickup.zone not in zones:
        raise DomainError(403, "outside_your_zones")
    assigned = advance_pickup(
        pickup, PickupStatus.ASSIGNED, by=uid, clock=clock, collectorUid=uid, assignedAt=clock.now()
    )
    _commit(store, clock, assigned, [])
    return _detail(store, assigned, uid)


def normalise_code(raw: str) -> str:
    return raw.strip().upper().replace(" ", "")


def scan(store: DataStore, clock: Clock, uid: str, pickup_id: str, raw_code: str) -> ScanResult:
    pickup = _my_active_pickup(store, uid, pickup_id)
    code = normalise_code(raw_code)
    if not is_valid_code(code):
        raise DomainError(422, "invalid_code")
    bag = store.get_bags([code]).get(code)
    if bag is None:
        raise DomainError(404, "unknown_code")
    if bag.pickupId != pickup.id or code not in pickup.bagCodes:
        raise DomainError(409, "wrong_pickup")
    slot = pickup.bagCodes.index(code) + 1

    if bag.status in SCANNED:
        return ScanResult(code=code, slot=slot, alreadyScanned=True, pickup=_detail(store, pickup, uid))

    collected = advance_bag(bag, BagStatus.COLLECTED, by=uid, clock=clock, collectorUid=uid)
    _commit(store, clock, pickup, [collected])
    return ScanResult(code=code, slot=slot, alreadyScanned=False, pickup=_detail(store, pickup, uid))


def simulate_scan(store: DataStore, clock: Clock, uid: str, pickup_id: str, slot: int) -> ScanResult:
    """Demo accounts only (checked by the route): scan the bag in `slot`."""
    pickup = _my_active_pickup(store, uid, pickup_id)
    if not 1 <= slot <= len(pickup.bagCodes):
        raise DomainError(422, "invalid_slot")
    return scan(store, clock, uid, pickup_id, pickup.bagCodes[slot - 1])


def _reason(raw: str | None) -> str | None:
    text = (raw or "").strip()
    if len(text) > MAX_REASON:
        raise DomainError(422, "reason_too_long")
    return text or None


def complete(
    store: DataStore, clock: Clock, uid: str, pickup_id: str, missing_reason: str | None = None
) -> CollectorPickupDetail:
    """All bags scanned, or some with a reason; unscanned bags go back to the resident."""
    pickup = _my_active_pickup(store, uid, pickup_id)
    bags = attached_bags(store, pickup)
    scanned = [b for b in bags if b.status in SCANNED]
    unscanned = [b for b in bags if b.status == BagStatus.SCHEDULED]
    if not scanned:
        raise DomainError(409, "nothing_scanned")
    reason = _reason(missing_reason)
    if unscanned and reason is None:
        raise DomainError(422, "missing_reason_required")

    released = release_bags(unscanned, by=uid, clock=clock)
    done = advance_pickup(
        pickup,
        PickupStatus.COLLECTED,
        by=uid,
        clock=clock,
        collectedAt=clock.now(),
        missingBagsReason=reason if unscanned else None,
    )
    _commit(store, clock, done, released)
    return _detail(store, done, uid)


def mark_missed(store: DataStore, clock: Clock, uid: str, pickup_id: str, reason: str) -> CollectorPickupDetail:
    """Resident not available: every bag goes back to `issued`."""
    pickup = _my_active_pickup(store, uid, pickup_id)
    text = _reason(reason)
    if text is None:
        raise DomainError(422, "reason_required")
    bags = attached_bags(store, pickup)
    if any(b.status in SCANNED for b in bags):
        raise DomainError(409, "bags_already_scanned")
    released = release_bags(bags, by=uid, clock=clock)
    missed = advance_pickup(pickup, PickupStatus.MISSED, by=uid, clock=clock, missedReason=text)
    _commit(store, clock, missed, released)
    return _detail(store, missed, uid)


# --- warehouse handover ---


def handover_list(store: DataStore, uid: str) -> list[HandoverPickup]:
    """Collected pickups not yet delivered, with their bags (codes known: scanned)."""
    pickups = store.list_collector_pickups(uid, status=PickupStatus.COLLECTED)
    households = store.get_households([p.householdId for p in pickups])
    result = []
    for pickup in sorted(pickups, key=lambda p: (p.date, SLOT_ORDER[p.timeSlot])):
        bags = attached_bags(store, pickup)
        household = households.get(pickup.householdId)
        result.append(
            HandoverPickup(
                pickupId=pickup.id,
                date=pickup.date,
                householdName=household.name if household else "Household",
                bags=[
                    BagSlot(slot=pickup.bagCodes.index(b.code) + 1, status=b.status, code=b.code)
                    for b in bags
                ],
            )
        )
    return result


def handover_scan(store: DataStore, clock: Clock, uid: str, raw_code: str) -> HandoverScanResult:
    code = normalise_code(raw_code)
    if not is_valid_code(code):
        raise DomainError(422, "invalid_code")
    bag = store.get_bags([code]).get(code)
    if bag is None:
        raise DomainError(404, "unknown_code")
    if bag.collectorUid != uid or bag.pickupId is None:
        raise DomainError(409, "not_in_your_van")
    pickup = store.get_pickup(bag.pickupId)
    if pickup is None:
        raise DomainError(409, "not_in_your_van")
    if bag.status in (BagStatus.AT_WAREHOUSE, BagStatus.PROCESSED):
        return HandoverScanResult(
            code=code,
            alreadyScanned=True,
            pickupId=pickup.id,
            pickupDelivered=pickup.status in (PickupStatus.DELIVERED, PickupStatus.PROCESSED),
        )
    if bag.status != BagStatus.COLLECTED or pickup.status != PickupStatus.COLLECTED:
        raise DomainError(409, "not_in_your_van")

    arrived = advance_bag(bag, BagStatus.AT_WAREHOUSE, by=uid, clock=clock)
    others = [b for b in attached_bags(store, pickup) if b.code != code]
    all_in = all(b.status in (BagStatus.AT_WAREHOUSE, BagStatus.PROCESSED) for b in others)
    if all_in:
        pickup = advance_pickup(
            pickup, PickupStatus.DELIVERED, by=uid, clock=clock, deliveredAt=clock.now()
        )
    _commit(store, clock, pickup, [arrived])
    return HandoverScanResult(code=code, alreadyScanned=False, pickupId=pickup.id, pickupDelivered=all_in)
