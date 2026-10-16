"""The one place that defines allowed pickup and bag status transitions.

Every status change in the API goes through `advance_pickup` / `advance_bag`,
which reject anything not listed here and append to `statusHistory`.

Pickup: requested -> assigned -> collected -> delivered -> processed
        requested | assigned -> cancelled      (resident)
        assigned -> missed                     (collector: resident not available)
Bag:    issued -> scheduled -> collected -> at_warehouse -> processed
        scheduled -> issued                    (pickup cancelled / missed / bag left behind)
"""

from typing import Any

from app.clock import Clock
from app.errors import DomainError
from app.models import Bag, BagStatus, Pickup, PickupStatus, StatusEvent

P, B = PickupStatus, BagStatus

PICKUP_TRANSITIONS: dict[PickupStatus, frozenset[PickupStatus]] = {
    P.REQUESTED: frozenset({P.ASSIGNED, P.CANCELLED}),
    P.ASSIGNED: frozenset({P.COLLECTED, P.MISSED, P.CANCELLED}),
    P.COLLECTED: frozenset({P.DELIVERED}),
    P.DELIVERED: frozenset({P.PROCESSED}),
    P.PROCESSED: frozenset(),
    P.CANCELLED: frozenset(),
    P.MISSED: frozenset(),
}

BAG_TRANSITIONS: dict[BagStatus, frozenset[BagStatus]] = {
    B.ISSUED: frozenset({B.SCHEDULED}),
    B.SCHEDULED: frozenset({B.COLLECTED, B.ISSUED}),
    B.COLLECTED: frozenset({B.AT_WAREHOUSE}),
    B.AT_WAREHOUSE: frozenset({B.PROCESSED}),
    B.PROCESSED: frozenset(),
}

# Pickup statuses that no longer hold a date (the resident may rebook that day).
INACTIVE_PICKUP_STATUSES = frozenset({P.CANCELLED, P.MISSED})


def can_advance_pickup(current: PickupStatus, to: PickupStatus) -> bool:
    return to in PICKUP_TRANSITIONS[current]


def can_advance_bag(current: BagStatus, to: BagStatus) -> bool:
    return to in BAG_TRANSITIONS[current]


def advance_pickup(
    pickup: Pickup, to: PickupStatus, *, by: str, clock: Clock, **updates: Any
) -> Pickup:
    if not can_advance_pickup(pickup.status, to):
        raise DomainError(409, "invalid_transition")
    event = StatusEvent(status=to, at=clock.now(), by=by)
    return pickup.model_copy(
        update={"status": to, "statusHistory": [*pickup.statusHistory, event], **updates}
    )


def advance_bag(bag: Bag, to: BagStatus, *, by: str, clock: Clock, **updates: Any) -> Bag:
    if not can_advance_bag(bag.status, to):
        raise DomainError(409, "invalid_transition")
    event = StatusEvent(status=to, at=clock.now(), by=by)
    return bag.model_copy(
        update={"status": to, "statusHistory": [*bag.statusHistory, event], **updates}
    )
