from datetime import date

from fastapi.testclient import TestClient

from app import services
from app.demo import ensure_demo_resident_data
from app.models import BagStatus, PickupStatus, TimeSlot
from tests.fakes import FakeDataStore, FixedClock

UID = "demo-resident"


def summary(store: FakeDataStore) -> dict[str, object]:
    pickups = store.list_pickups(UID)
    return {
        "bags": len(store.list_bags(UID)),
        "issued": sum(b.status == BagStatus.ISSUED for b in store.list_bags(UID)),
        "active": sum(p.status == PickupStatus.REQUESTED for p in pickups),
        "cancelled": sum(p.status == PickupStatus.CANCELLED for p in pickups),
    }


def test_seeds_household_bags_and_pickups() -> None:
    store, clock = FakeDataStore(), FixedClock()
    ensure_demo_resident_data(store, clock)
    assert store.get_household(UID) is not None
    assert summary(store) == {"bags": 10, "issued": 8, "active": 1, "cancelled": 1}
    upcoming = next(p for p in store.list_pickups(UID) if p.status == PickupStatus.REQUESTED)
    assert upcoming.date == "2026-03-13"
    assert len(upcoming.bagCodes) == 2


def test_is_idempotent() -> None:
    store, clock = FakeDataStore(), FixedClock()
    ensure_demo_resident_data(store, clock)
    snapshot = (dict(store.bags), dict(store.pickups), dict(store.households))
    ensure_demo_resident_data(store, clock)
    assert (store.bags, store.pickups, store.households) == snapshot


def test_never_deletes_user_activity_and_tops_up() -> None:
    store, clock = FakeDataStore(), FixedClock()
    ensure_demo_resident_data(store, clock)
    # A judge books every remaining bag across pickups.
    free = [b.code for b in store.list_bags(UID) if b.status == BagStatus.ISSUED]
    for i, chunk in enumerate([free[:5], free[5:]]):
        services.schedule_pickup(
            store,
            clock,
            UID,
            pickup_date=date(2026, 3, 20 + i),
            time_slot=TimeSlot.MORNING,
            bag_codes=chunk,
        )
    pickups_before = set(store.pickups)
    ensure_demo_resident_data(store, clock)
    assert set(store.pickups) == pickups_before  # nothing removed or added
    assert summary(store)["issued"] == 5  # topped back up


def test_creates_new_upcoming_pickup_when_old_one_is_past() -> None:
    store, clock = FakeDataStore(), FixedClock()
    ensure_demo_resident_data(store, clock)
    clock.advance(days=7)  # the seeded pickup (03-13) is now in the past
    ensure_demo_resident_data(store, clock)
    upcoming = [
        p for p in store.list_pickups(UID)
        if p.status == PickupStatus.REQUESTED and p.date >= "2026-03-18"
    ]
    assert len(upcoming) == 1


def test_demo_resident_sign_in_repairs_data(client: TestClient, store: FakeDataStore) -> None:
    assert client.post("/auth/demo/resident").status_code == 200
    assert summary(store)["active"] == 1
    assert client.post("/auth/demo/collector").status_code == 200
    assert store.get_household("demo-collector") is None
