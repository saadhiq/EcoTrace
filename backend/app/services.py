"""Resident flow business rules: households, bags and pickups."""

from datetime import date, timedelta

from app.bagcodes import generate_code
from app.clock import Clock, local_today
from app.errors import DomainError
from app.models import (
    CANCELLABLE_PICKUP_STATUSES,
    Bag,
    BagStatus,
    Consent,
    Household,
    Pickup,
    PickupStatus,
    RouteStop,
    StatusEvent,
    TimeSlot,
)
from app.store import DataStore
from app.transitions import INACTIVE_PICKUP_STATUSES, advance_bag, advance_pickup
from app.zones import ZONE_IDS

__all__ = ["DomainError"]

STARTER_BAGS = 5
BAGS_PER_REQUEST = 5
MAX_UNUSED_BAGS = 20
MAX_BAGS_PER_PICKUP = 5
MAX_DAYS_AHEAD = 14
_CODE_ATTEMPTS = 5


def _require_zone(zone: str) -> None:
    if zone not in ZONE_IDS:
        raise DomainError(422, "invalid_zone")


# --- households ---


def create_household(
    store: DataStore,
    clock: Clock,
    uid: str,
    *,
    name: str,
    phone: str,
    address_line: str,
    zone: str,
    lat: float | None = None,
    lng: float | None = None,
) -> tuple[Household, list[Bag]]:
    """Create the resident's (only) household and issue the starter bags."""
    _require_zone(zone)
    household = Household(
        id=uid,
        ownerUid=uid,
        name=name,
        phone=phone,
        addressLine=address_line,
        zone=zone,
        lat=lat,
        lng=lng,
        consent=Consent(dataSharing=False, updatedAt=clock.now()),
        createdAt=clock.now(),
    )
    if not store.create_household(household):
        raise DomainError(409, "household_exists")
    bags = issue_bags(store, clock, household, STARTER_BAGS, by=uid)
    return household, bags


def get_household(store: DataStore, uid: str) -> Household:
    household = store.get_household(uid)
    if household is None:
        raise DomainError(404, "no_household")
    return household


def update_household(
    store: DataStore, clock: Clock, uid: str, changes: dict[str, object]
) -> Household:
    """Apply profile changes. A `dataSharing` change also logs consentHistory
    (same batch), exactly like PUT /households/me/consent."""
    from app.residents import consent_change

    household = get_household(store, uid)
    if "zone" in changes:
        _require_zone(str(changes["zone"]))
    sharing = changes.pop("dataSharing", None)
    updated = Household.model_validate({**household.model_dump(), **changes})
    entry = None
    if sharing is not None:
        change = consent_change(updated, bool(sharing), clock, by=uid)
        if change is not None:
            updated, entry = change
    store.commit([], [], households=[updated], consent=[(uid, entry)] if entry else None)
    return updated


# --- bags ---


def issue_bags(store: DataStore, clock: Clock, household: Household, count: int, by: str) -> list[Bag]:
    """Create `count` new bags with fresh random codes (retries on a collision)."""
    for _ in range(_CODE_ATTEMPTS):
        codes = {generate_code() for _ in range(count)}
        if len(codes) < count:
            continue
        now = clock.now()
        bags = [
            Bag(
                code=code,
                householdId=household.id,
                ownerUid=household.ownerUid,
                status=BagStatus.ISSUED,
                issuedAt=now,
                statusHistory=[StatusEvent(status=BagStatus.ISSUED, at=now, by=by)],
            )
            for code in sorted(codes)
        ]
        if store.create_bags(bags):
            return bags
    raise DomainError(503, "bag_code_unavailable")


def list_bags(store: DataStore, uid: str) -> list[Bag]:
    return store.list_bags(get_household(store, uid).id)


def request_more_bags(store: DataStore, clock: Clock, uid: str) -> list[Bag]:
    """Issue up to 5 more bags without exceeding 20 unused (issued) bags."""
    household = get_household(store, uid)
    unused = sum(1 for bag in store.list_bags(household.id) if bag.status == BagStatus.ISSUED)
    room = MAX_UNUSED_BAGS - unused
    if room <= 0:
        raise DomainError(409, "bag_limit_reached")
    return issue_bags(store, clock, household, min(BAGS_PER_REQUEST, room), by=uid)


# --- pickups ---


def pickup_date_window(clock: Clock) -> tuple[date, date]:
    """Bookable dates: tomorrow through 14 days ahead (Colombo time)."""
    today = local_today(clock)
    return today + timedelta(days=1), today + timedelta(days=MAX_DAYS_AHEAD)


def attached_bags(store: DataStore, pickup: Pickup) -> list[Bag]:
    """The pickup's bags that still belong to it (released bags are excluded)."""
    bags = store.get_bags(pickup.bagCodes)
    return [bags[c] for c in pickup.bagCodes if c in bags and bags[c].pickupId == pickup.id]


def route_stop(pickup: Pickup, household: Household | None, bags: list[Bag], clock: Clock) -> RouteStop:
    """Code-free mirror of an assigned pickup for the collector's live route."""
    assert pickup.collectorUid is not None
    scanned = {BagStatus.COLLECTED, BagStatus.AT_WAREHOUSE, BagStatus.PROCESSED}
    return RouteStop(
        pickupId=pickup.id,
        collectorUid=pickup.collectorUid,
        date=pickup.date,
        timeSlot=pickup.timeSlot,
        status=pickup.status,
        zone=pickup.zone,
        householdName=household.name if household else "Household",
        addressLine=household.addressLine if household else "",
        bagCount=len(bags) if pickup.status != PickupStatus.REQUESTED else len(pickup.bagCodes),
        scannedCount=sum(1 for b in bags if b.status in scanned),
        updatedAt=clock.now(),
    )


def schedule_pickup(
    store: DataStore,
    clock: Clock,
    uid: str,
    *,
    pickup_date: date,
    time_slot: TimeSlot,
    bag_codes: list[str],
    notes: str = "",
    by: str | None = None,
    demo_override: bool = False,
) -> Pickup:
    """Validate, then write the pickup and its bags in one batch.

    `demo_override` (seed data only) skips the date window and the
    one-pickup-per-date rule so demo collectors always have work today.
    """
    household = get_household(store, uid)

    first, last = pickup_date_window(clock)
    if not demo_override and not first <= pickup_date <= last:
        raise DomainError(422, "date_out_of_range")
    if not 1 <= len(bag_codes) <= MAX_BAGS_PER_PICKUP:
        raise DomainError(422, "invalid_bag_count")
    if len(set(bag_codes)) != len(bag_codes):
        raise DomainError(422, "duplicate_bags")

    day = pickup_date.isoformat()
    if not demo_override and any(
        p.date == day and p.status not in INACTIVE_PICKUP_STATUSES
        for p in store.list_pickups(household.id)
    ):
        raise DomainError(409, "pickup_exists_for_date")

    bags = store.get_bags(bag_codes)
    for code in bag_codes:
        bag = bags.get(code)
        # Same error for "missing" and "someone else's" so codes can't be probed.
        if bag is None or bag.householdId != household.id:
            raise DomainError(422, "bag_not_owned")
        if bag.status != BagStatus.ISSUED or bag.pickupId is not None:
            raise DomainError(409, "bag_not_available")

    actor = by or uid
    now = clock.now()
    pickup = Pickup(
        id=store.new_pickup_id(),
        householdId=household.id,
        residentUid=household.ownerUid,
        zone=household.zone,
        date=day,
        timeSlot=time_slot,
        bagCodes=list(bag_codes),
        notes=notes.strip(),
        status=PickupStatus.REQUESTED,
        collectorUid=None,
        statusHistory=[StatusEvent(status=PickupStatus.REQUESTED, at=now, by=actor)],
        createdAt=now,
    )
    updated_bags = [
        advance_bag(bags[code], BagStatus.SCHEDULED, by=actor, clock=clock, pickupId=pickup.id)
        for code in bag_codes
    ]
    store.commit([pickup], updated_bags)
    return pickup


def list_pickups(store: DataStore, uid: str) -> list[Pickup]:
    return store.list_pickups(get_household(store, uid).id)


def release_bags(bags: list[Bag], *, by: str, clock: Clock) -> list[Bag]:
    """Scheduled bags go back to `issued` (unattached) so they can be reused."""
    return [
        advance_bag(bag, BagStatus.ISSUED, by=by, clock=clock, pickupId=None)
        for bag in bags
        if bag.status == BagStatus.SCHEDULED
    ]


def cancel_pickup(
    store: DataStore, clock: Clock, uid: str, pickup_id: str, by: str | None = None
) -> Pickup:
    """Cancel while requested/assigned and before any bag is scanned."""
    pickup = store.get_pickup(pickup_id)
    if pickup is None or pickup.residentUid != uid:
        raise DomainError(404, "pickup_not_found")
    if pickup.status not in CANCELLABLE_PICKUP_STATUSES:
        raise DomainError(409, "not_cancellable")
    bags = attached_bags(store, pickup)
    if any(b.status != BagStatus.SCHEDULED for b in bags):
        # A collector has already scanned a bag: it is physically in the van.
        raise DomainError(409, "not_cancellable")

    actor = by or uid
    cancelled = advance_pickup(pickup, PickupStatus.CANCELLED, by=actor, clock=clock)
    released = release_bags(bags, by=actor, clock=clock)
    routes = []
    if cancelled.collectorUid:
        routes.append(route_stop(cancelled, store.get_household(pickup.householdId), [], clock))
    store.commit([cancelled], released, routes)
    return cancelled
