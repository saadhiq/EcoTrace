from datetime import UTC, datetime
from itertools import product

import pytest

from app.errors import DomainError
from app.models import Bag, BagStatus, Pickup, PickupStatus, TimeSlot
from app.transitions import (
    BAG_TRANSITIONS,
    PICKUP_TRANSITIONS,
    advance_bag,
    advance_pickup,
)
from tests.fakes import FixedClock

P, B = PickupStatus, BagStatus

VALID_PICKUP = {
    (P.REQUESTED, P.ASSIGNED),
    (P.REQUESTED, P.CANCELLED),
    (P.ASSIGNED, P.COLLECTED),
    (P.ASSIGNED, P.MISSED),
    (P.ASSIGNED, P.CANCELLED),
    (P.COLLECTED, P.DELIVERED),
    (P.DELIVERED, P.PROCESSED),
}
VALID_BAG = {
    (B.ISSUED, B.SCHEDULED),
    (B.SCHEDULED, B.COLLECTED),
    (B.SCHEDULED, B.ISSUED),
    (B.COLLECTED, B.AT_WAREHOUSE),
    (B.AT_WAREHOUSE, B.PROCESSED),
}
NOW = datetime(2026, 3, 10, tzinfo=UTC)


def pickup(status: PickupStatus) -> Pickup:
    return Pickup(
        id="p1", householdId="h", residentUid="h", zone="colombo-07", date="2026-03-11",
        timeSlot=TimeSlot.MORNING, bagCodes=["ECO-2222-22"], status=status, createdAt=NOW,
    )


def bag(status: BagStatus) -> Bag:
    return Bag(code="ECO-2222-22", householdId="h", ownerUid="h", status=status, issuedAt=NOW)


def test_tables_cover_every_status() -> None:
    assert set(PICKUP_TRANSITIONS) == set(PickupStatus)
    assert set(BAG_TRANSITIONS) == set(BagStatus)


def test_table_matches_documented_transitions() -> None:
    assert {(a, b) for a, tos in PICKUP_TRANSITIONS.items() for b in tos} == VALID_PICKUP
    assert {(a, b) for a, tos in BAG_TRANSITIONS.items() for b in tos} == VALID_BAG


@pytest.mark.parametrize("current,target", list(product(PickupStatus, PickupStatus)))
def test_every_pickup_transition(current: PickupStatus, target: PickupStatus) -> None:
    if (current, target) in VALID_PICKUP:
        moved = advance_pickup(pickup(current), target, by="u", clock=FixedClock())
        assert moved.status == target
        assert moved.statusHistory[-1].status == target
        assert moved.statusHistory[-1].by == "u"
    else:
        with pytest.raises(DomainError) as err:
            advance_pickup(pickup(current), target, by="u", clock=FixedClock())
        assert (err.value.status, err.value.detail) == (409, "invalid_transition")


@pytest.mark.parametrize("current,target", list(product(BagStatus, BagStatus)))
def test_every_bag_transition(current: BagStatus, target: BagStatus) -> None:
    if (current, target) in VALID_BAG:
        assert advance_bag(bag(current), target, by="u", clock=FixedClock()).status == target
    else:
        with pytest.raises(DomainError) as err:
            advance_bag(bag(current), target, by="u", clock=FixedClock())
        assert err.value.detail == "invalid_transition"


def test_advance_applies_extra_updates_and_keeps_history() -> None:
    first = advance_pickup(pickup(P.REQUESTED), P.ASSIGNED, by="c1", clock=FixedClock(), collectorUid="c1")
    second = advance_pickup(first, P.COLLECTED, by="c1", clock=FixedClock())
    assert second.collectorUid == "c1"
    assert [e.status for e in second.statusHistory] == ["assigned", "collected"]
