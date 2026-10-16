"""Resident flow business rules: households, bags and pickups."""

from datetime import date, timedelta

from app.bagcodes import generate_code
from app.clock import Clock, local_today
from app.models import (
    CANCELLABLE_PICKUP_STATUSES,
    Bag,
    BagStatus,
    Consent,
    Household,
    Pickup,
    PickupStatus,
    StatusEvent,
    TimeSlot,
)
from app.store import DataStore
from app.zones import ZONE_IDS

STARTER_BAGS = 5
BAGS_PER_REQUEST = 5
MAX_UNUSED_BAGS = 20
MAX_BAGS_PER_PICKUP = 5
MAX_DAYS_AHEAD = 14
_CODE_ATTEMPTS = 5


class DomainError(Exception):
    """A rule violation, mapped to an HTTP error by the API layer."""

    def __init__(self, status: int, detail: str) -> None:
        super().__init__(detail)
        self.status = status
        self.detail = detail


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
    """Apply profile changes; `dataSharing` updates consent and its timestamp."""
    household = get_household(store, uid)
    if "zone" in changes:
        _require_zone(str(changes["zone"]))
    data = household.model_dump()
    if "dataSharing" in changes:
        sharing = bool(changes.pop("dataSharing"))
        if sharing != household.consent.dataSharing:
            data["consent"] = {"dataSharing": sharing, "updatedAt": clock.now()}
    data.update(changes)
    updated = Household.model_validate(data)
    store.save_household(updated)
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
) -> Pickup:
    household = get_household(store, uid)

    first, last = pickup_date_window(clock)
    if not first <= pickup_date <= last:
        raise DomainError(422, "date_out_of_range")
    if not 1 <= len(bag_codes) <= MAX_BAGS_PER_PICKUP:
        raise DomainError(422, "invalid_bag_count")
    if len(set(bag_codes)) != len(bag_codes):
        raise DomainError(422, "duplicate_bags")

    day = pickup_date.isoformat()
    if any(p.date == day and p.status != PickupStatus.CANCELLED for p in store.list_pickups(household.id)):
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
        bags[code].model_copy(
            update={
                "status": BagStatus.SCHEDULED,
                "pickupId": pickup.id,
                "statusHistory": [
                    *bags[code].statusHistory,
                    StatusEvent(status=BagStatus.SCHEDULED, at=now, by=actor),
                ],
            }
        )
        for code in bag_codes
    ]
    store.commit([pickup], updated_bags)
    return pickup


def list_pickups(store: DataStore, uid: str) -> list[Pickup]:
    return store.list_pickups(get_household(store, uid).id)


def cancel_pickup(
    store: DataStore, clock: Clock, uid: str, pickup_id: str, by: str | None = None
) -> Pickup:
    """Cancel while requested/assigned; its bags go back to `issued`."""
    pickup = store.get_pickup(pickup_id)
    if pickup is None or pickup.residentUid != uid:
        raise DomainError(404, "pickup_not_found")
    if pickup.status not in CANCELLABLE_PICKUP_STATUSES:
        raise DomainError(409, "not_cancellable")

    actor = by or uid
    now = clock.now()
    cancelled = pickup.model_copy(
        update={
            "status": PickupStatus.CANCELLED,
            "statusHistory": [
                *pickup.statusHistory,
                StatusEvent(status=PickupStatus.CANCELLED, at=now, by=actor),
            ],
        }
    )
    released = [
        bag.model_copy(
            update={
                "status": BagStatus.ISSUED,
                "pickupId": None,
                "statusHistory": [
                    *bag.statusHistory,
                    StatusEvent(status=BagStatus.ISSUED, at=now, by=actor),
                ],
            }
        )
        for bag in store.get_bags(pickup.bagCodes).values()
        # Only bags still attached to this pickup.
        if bag.pickupId == pickup.id and bag.status == BagStatus.SCHEDULED
    ]
    store.commit([cancelled], released)
    return cancelled
