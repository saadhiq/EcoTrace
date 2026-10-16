from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.models import BagStatus, PickupStatus
from tests.fakes import FakeDataStore, FakeIdentity, FixedClock
from tests.helpers import onboard, resident

# FixedClock: today in Colombo is 2026-03-10.
TOMORROW = "2026-03-11"
LAST_DAY = "2026-03-24"


@pytest.fixture
def home(client: TestClient, identity: FakeIdentity) -> dict[str, Any]:
    result = onboard(client, identity)
    result["codes"] = [b["code"] for b in result["bags"]]
    return result


def book(client: TestClient, home: dict[str, Any], **overrides: Any):  # noqa: ANN201
    body = {"date": TOMORROW, "timeSlot": "morning", "bagCodes": home["codes"][:2], **overrides}
    return client.post("/pickups", json=body, headers=home["headers"])


def detail(response) -> str:  # noqa: ANN001
    return response.json()["detail"]


# --- happy path ---


def test_schedule_pickup(client: TestClient, home: dict, store: FakeDataStore) -> None:
    response = book(client, home, notes="  by the gate ")
    assert response.status_code == 201
    pickup = response.json()
    assert pickup["status"] == "requested"
    assert pickup["zone"] == "colombo-05"
    assert pickup["residentUid"] == "res-1"
    assert pickup["collectorUid"] is None
    assert pickup["notes"] == "by the gate"
    assert [e["status"] for e in pickup["statusHistory"]] == ["requested"]
    for code in home["codes"][:2]:
        assert store.bags[code].status == BagStatus.SCHEDULED
        assert store.bags[code].pickupId == pickup["id"]
    for code in home["codes"][2:]:
        assert store.bags[code].status == BagStatus.ISSUED


def test_pickup_and_bags_are_written_in_one_batch(
    client: TestClient, home: dict, store: FakeDataStore
) -> None:
    before = store.commits
    book(client, home)
    assert store.commits == before + 1


def test_pickups_mine_lists_newest_date_first(client: TestClient, home: dict) -> None:
    book(client, home, date=TOMORROW, bagCodes=home["codes"][:1])
    book(client, home, date="2026-03-15", bagCodes=home["codes"][1:2])
    dates = [p["date"] for p in client.get("/pickups/mine", headers=home["headers"]).json()]
    assert dates == ["2026-03-15", TOMORROW]


# --- date window ---


@pytest.mark.parametrize("day", ["2026-03-09", "2026-03-10", "2026-03-25", "2027-01-01"])
def test_dates_outside_window_are_rejected(client: TestClient, home: dict, day: str) -> None:
    response = book(client, home, date=day)
    assert response.status_code == 422
    assert detail(response) == "date_out_of_range"


@pytest.mark.parametrize("day", [TOMORROW, "2026-03-17", LAST_DAY])
def test_dates_inside_window_are_accepted(client: TestClient, home: dict, day: str) -> None:
    assert book(client, home, date=day).status_code == 201


def test_window_uses_colombo_time(client: TestClient, home: dict, clock: FixedClock) -> None:
    # 2026-03-10 19:00 UTC is already 2026-03-11 00:30 in Colombo.
    clock.advance(hours=15, minutes=30)
    response = book(client, home, date=TOMORROW)
    assert response.status_code == 422
    assert book(client, home, date="2026-03-12").status_code == 201


def test_invalid_date_format_is_rejected(client: TestClient, home: dict) -> None:
    assert book(client, home, date="11/03/2026").status_code == 422


# --- bags ---


def test_zero_bags_rejected(client: TestClient, home: dict) -> None:
    assert book(client, home, bagCodes=[]).status_code == 422


def test_six_bags_rejected(client: TestClient, home: dict) -> None:
    more = client.post("/bags/request-more", headers=home["headers"]).json()
    codes = home["codes"] + [b["code"] for b in more][:1]
    assert book(client, home, bagCodes=codes).status_code == 422


def test_five_bags_accepted(client: TestClient, home: dict) -> None:
    assert book(client, home, bagCodes=home["codes"]).status_code == 201


def test_duplicate_bag_codes_rejected(client: TestClient, home: dict) -> None:
    code = home["codes"][0]
    response = book(client, home, bagCodes=[code, code])
    assert response.status_code == 422
    assert detail(response) == "duplicate_bags"


def test_unknown_bag_rejected(client: TestClient, home: dict) -> None:
    response = book(client, home, bagCodes=["ECO-2222-22"])
    assert response.status_code == 422
    assert detail(response) == "bag_not_owned"


def test_other_households_bag_rejected(
    client: TestClient, identity: FakeIdentity, home: dict
) -> None:
    other = onboard(client, identity, "res-2")
    response = book(client, home, bagCodes=[home["codes"][0], other["bags"][0]["code"]])
    assert response.status_code == 422
    assert detail(response) == "bag_not_owned"


def test_bag_codes_are_normalised(client: TestClient, home: dict) -> None:
    response = book(client, home, bagCodes=[f" {home['codes'][0].lower()} "])
    assert response.status_code == 201


@pytest.mark.parametrize("bag_status", [s for s in BagStatus if s != BagStatus.ISSUED])
def test_non_issued_bag_rejected(
    client: TestClient, home: dict, store: FakeDataStore, bag_status: BagStatus
) -> None:
    code = home["codes"][0]
    store.bags[code] = store.bags[code].model_copy(update={"status": bag_status})
    response = book(client, home, bagCodes=[code])
    assert response.status_code == 409
    assert detail(response) == "bag_not_available"


def test_bag_cannot_be_in_two_pickups(client: TestClient, home: dict) -> None:
    assert book(client, home, date=TOMORROW).status_code == 201
    response = book(client, home, date="2026-03-12")  # same two bags
    assert response.status_code == 409
    assert detail(response) == "bag_not_available"


def test_failed_validation_writes_nothing(client: TestClient, home: dict, store: FakeDataStore) -> None:
    before = (store.commits, dict(store.bags))
    book(client, home, bagCodes=[home["codes"][0], "ECO-2222-22"])
    assert (store.commits, store.bags) == before
    assert store.pickups == {}


# --- one per date ---


def test_one_active_pickup_per_date(client: TestClient, home: dict) -> None:
    assert book(client, home, bagCodes=home["codes"][:1]).status_code == 201
    response = book(client, home, bagCodes=home["codes"][1:2])
    assert response.status_code == 409
    assert detail(response) == "pickup_exists_for_date"


def test_date_frees_up_after_cancel(client: TestClient, home: dict) -> None:
    first = book(client, home).json()
    client.post(f"/pickups/{first['id']}/cancel", headers=home["headers"])
    assert book(client, home).status_code == 201


def test_other_households_can_book_same_date(
    client: TestClient, identity: FakeIdentity, home: dict
) -> None:
    other = onboard(client, identity, "res-2")
    other["codes"] = [b["code"] for b in other["bags"]]
    assert book(client, home).status_code == 201
    assert book(client, other).status_code == 201


def test_schedule_requires_household(client: TestClient, identity: FakeIdentity) -> None:
    body = {"date": TOMORROW, "timeSlot": "morning", "bagCodes": ["ECO-2222-22"]}
    response = client.post("/pickups", json=body, headers=resident(identity, "new"))
    assert response.status_code == 404


def test_invalid_slot_and_long_notes_rejected(client: TestClient, home: dict) -> None:
    assert book(client, home, timeSlot="evening").status_code == 422
    assert book(client, home, notes="x" * 281).status_code == 422


# --- cancel ---


def test_cancel_returns_bags_to_issued(client: TestClient, home: dict, store: FakeDataStore) -> None:
    pickup = book(client, home).json()
    response = client.post(f"/pickups/{pickup['id']}/cancel", headers=home["headers"])
    assert response.status_code == 200
    assert response.json()["status"] == "cancelled"
    assert [e["status"] for e in response.json()["statusHistory"]] == ["requested", "cancelled"]
    for code in home["codes"][:2]:
        bag = store.bags[code]
        assert bag.status == BagStatus.ISSUED
        assert bag.pickupId is None
        assert [e.status for e in bag.statusHistory] == ["issued", "scheduled", "issued"]


def test_cancelled_bags_can_be_rebooked(client: TestClient, home: dict) -> None:
    pickup = book(client, home).json()
    client.post(f"/pickups/{pickup['id']}/cancel", headers=home["headers"])
    assert book(client, home, date="2026-03-13").status_code == 201


def test_cancel_allowed_while_assigned(client: TestClient, home: dict, store: FakeDataStore) -> None:
    pickup = book(client, home).json()
    store.pickups[pickup["id"]] = store.pickups[pickup["id"]].model_copy(
        update={"status": PickupStatus.ASSIGNED}
    )
    response = client.post(f"/pickups/{pickup['id']}/cancel", headers=home["headers"])
    assert response.status_code == 200


@pytest.mark.parametrize(
    "pickup_status",
    [PickupStatus.COLLECTED, PickupStatus.DELIVERED, PickupStatus.PROCESSED, PickupStatus.CANCELLED],
)
def test_cancel_rejected_after_collection(
    client: TestClient, home: dict, store: FakeDataStore, pickup_status: PickupStatus
) -> None:
    pickup = book(client, home).json()
    store.pickups[pickup["id"]] = store.pickups[pickup["id"]].model_copy(
        update={"status": pickup_status}
    )
    response = client.post(f"/pickups/{pickup['id']}/cancel", headers=home["headers"])
    assert response.status_code == 409
    assert detail(response) == "not_cancellable"


def test_cancel_only_releases_bags_still_attached(
    client: TestClient, home: dict, store: FakeDataStore
) -> None:
    pickup = book(client, home).json()
    code = home["codes"][0]
    # Simulate a bag that has already moved on (e.g. collected separately).
    store.bags[code] = store.bags[code].model_copy(update={"status": BagStatus.COLLECTED})
    client.post(f"/pickups/{pickup['id']}/cancel", headers=home["headers"])
    assert store.bags[code].status == BagStatus.COLLECTED
    assert store.bags[home["codes"][1]].status == BagStatus.ISSUED


def test_cannot_cancel_someone_elses_pickup(
    client: TestClient, identity: FakeIdentity, home: dict
) -> None:
    pickup = book(client, home).json()
    other = onboard(client, identity, "res-2")
    response = client.post(f"/pickups/{pickup['id']}/cancel", headers=other["headers"])
    assert response.status_code == 404


def test_cancel_unknown_pickup_is_404(client: TestClient, home: dict) -> None:
    assert client.post("/pickups/nope/cancel", headers=home["headers"]).status_code == 404


def test_non_residents_cannot_schedule(client: TestClient, identity: FakeIdentity, home: dict) -> None:
    identity.issue("col", "col-1", role="collector")
    body = {"date": TOMORROW, "timeSlot": "morning", "bagCodes": home["codes"][:1]}
    assert client.post("/pickups", json=body, headers={"Authorization": "Bearer col"}).status_code == 403
