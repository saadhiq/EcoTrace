from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.bagcodes import generate_code
from app.demo import ensure_demo_collector_data
from app.models import BagStatus, PickupStatus, Role
from tests.fakes import FakeDataStore, FakeIdentity, FakeUserStore, FixedClock
from tests.helpers import HOUSEHOLD, auth, onboard

TOMORROW = "2026-03-11"


def make_collector(
    identity: FakeIdentity, users: FakeUserStore, uid: str, zones: list[str]
) -> dict[str, str]:
    users.upsert(uid, f"Collector {uid}", f"{uid}@example.com", Role.COLLECTOR)
    users.set_zones(uid, zones)
    identity.issue(f"tok-{uid}", uid, role="collector")
    return auth(f"tok-{uid}")


@pytest.fixture
def world(client: TestClient, identity: FakeIdentity, users: FakeUserStore) -> dict[str, Any]:
    """A resident (colombo-05) with a 3-bag pickup tomorrow, and collectors."""
    home = onboard(client, identity, "res-1")
    codes = [b["code"] for b in home["bags"]]
    body = {"date": TOMORROW, "timeSlot": "afternoon", "bagCodes": codes[:3], "notes": "Gate"}
    pickup = client.post("/pickups", json=body, headers=home["headers"]).json()
    return {
        "home": home,
        "codes": codes,
        "pickup": pickup,
        "pid": pickup["id"],
        "col": make_collector(identity, users, "col-1", ["colombo-05", "colombo-07"]),
        "rival": make_collector(identity, users, "col-2", ["colombo-05"]),
        "far": make_collector(identity, users, "col-3", ["nugegoda"]),
    }


def day(client: TestClient, headers: dict[str, str], date: str = TOMORROW) -> dict[str, Any]:
    response = client.get(f"/collector/pickups?date={date}", headers=headers)
    assert response.status_code == 200, response.text
    return response.json()


def accept(client: TestClient, w: dict[str, Any], who: str = "col"):  # noqa: ANN201
    return client.post(f"/collector/pickups/{w['pid']}/accept", headers=w[who])


def scan(client: TestClient, w: dict[str, Any], code: str, who: str = "col"):  # noqa: ANN201
    return client.post(f"/collector/pickups/{w['pid']}/scan", json={"code": code}, headers=w[who])


def detail(response) -> str:  # noqa: ANN001
    return response.json()["detail"]


# --- day list ---


def test_available_lists_requested_pickups_in_my_zones_without_codes(
    client: TestClient, world: dict
) -> None:
    view = day(client, world["col"])
    assert view["zones"] == ["colombo-05", "colombo-07"]
    assert [p["id"] for p in view["available"]] == [world["pid"]]
    item = view["available"][0]
    assert item["householdName"] == HOUSEHOLD["name"]
    assert item["addressLine"] == HOUSEHOLD["addressLine"]
    assert item["phone"] == HOUSEHOLD["phone"]
    assert item["bagCount"] == 3
    assert item["mine"] is False
    assert not any(code in str(view) for code in world["codes"])


def test_out_of_zone_collector_sees_nothing(client: TestClient, world: dict) -> None:
    assert day(client, world["far"])["available"] == []


def test_other_dates_are_separate(client: TestClient, world: dict) -> None:
    assert day(client, world["col"], "2026-03-12")["available"] == []


def test_list_is_sorted_morning_first(
    client: TestClient, identity: FakeIdentity, world: dict
) -> None:
    other = onboard(client, identity, "res-2")
    body = {"date": TOMORROW, "timeSlot": "morning", "bagCodes": [other["bags"][0]["code"]]}
    morning = client.post("/pickups", json=body, headers=other["headers"]).json()
    ids = [p["id"] for p in day(client, world["col"])["available"]]
    assert ids == [morning["id"], world["pid"]]


def test_default_date_is_today_in_colombo(client: TestClient, world: dict) -> None:
    response = client.get("/collector/pickups", headers=world["col"])
    assert response.status_code == 200
    assert response.json()["date"] == "2026-03-10"


def test_non_collectors_are_rejected(client: TestClient, world: dict, identity: FakeIdentity) -> None:
    assert client.get("/collector/pickups", headers=world["home"]["headers"]).status_code == 403
    identity.issue("adm", "adm-1", role="admin")
    assert client.get("/collector/pickups", headers=auth("adm")).status_code == 403
    assert client.get("/collector/pickups").status_code == 401


# --- accept ---


def test_accept_assigns_to_me_and_writes_route_mirror(
    client: TestClient, world: dict, store: FakeDataStore
) -> None:
    response = accept(client, world)
    assert response.status_code == 200
    assert response.json()["status"] == "assigned"
    assert response.json()["mine"] is True
    pickup = store.pickups[world["pid"]]
    assert pickup.collectorUid == "col-1"
    assert pickup.assignedAt is not None
    route = store.routes[world["pid"]]
    assert (route.collectorUid, route.status, route.bagCount, route.scannedCount) == (
        "col-1", PickupStatus.ASSIGNED, 3, 0
    )
    assert route.householdName == HOUSEHOLD["name"]
    assert not any(code in route.model_dump_json() for code in world["codes"])

    view = day(client, world["col"])
    assert view["available"] == []
    assert [p["id"] for p in view["mine"]] == [world["pid"]]
    assert day(client, world["rival"])["available"] == []


def test_accept_is_idempotent_for_the_same_collector(client: TestClient, world: dict) -> None:
    accept(client, world)
    assert accept(client, world).status_code == 200


def test_accept_taken_pickup_is_rejected(client: TestClient, world: dict) -> None:
    accept(client, world)
    response = accept(client, world, "rival")
    assert response.status_code == 409
    assert detail(response) == "pickup_not_available"


def test_accept_outside_zones_is_rejected(client: TestClient, world: dict) -> None:
    response = accept(client, world, "far")
    assert response.status_code == 403
    assert detail(response) == "outside_your_zones"


def test_accept_cancelled_pickup_is_rejected(client: TestClient, world: dict) -> None:
    client.post(f"/pickups/{world['pid']}/cancel", headers=world["home"]["headers"])
    assert accept(client, world).status_code == 409


def test_detail_hides_codes_until_scanned(client: TestClient, world: dict) -> None:
    accept(client, world)
    slots = client.get(f"/collector/pickups/{world['pid']}", headers=world["col"]).json()["slots"]
    assert [s["code"] for s in slots] == [None, None, None]
    scan(client, world, world["codes"][1])
    slots = client.get(f"/collector/pickups/{world['pid']}", headers=world["col"]).json()["slots"]
    assert [s["code"] for s in slots] == [None, world["codes"][1], None]
    assert [s["status"] for s in slots] == ["scheduled", "collected", "scheduled"]


def test_detail_not_visible_to_out_of_zone_or_rival(client: TestClient, world: dict) -> None:
    assert client.get(f"/collector/pickups/{world['pid']}", headers=world["far"]).status_code == 404
    accept(client, world)
    assert client.get(f"/collector/pickups/{world['pid']}", headers=world["rival"]).status_code == 404


# --- scan ---


def test_scan_marks_bag_collected(client: TestClient, world: dict, store: FakeDataStore) -> None:
    accept(client, world)
    response = scan(client, world, f"  {world['codes'][0].lower()} ")
    assert response.status_code == 200
    body = response.json()
    assert (body["code"], body["slot"], body["alreadyScanned"]) == (world["codes"][0], 1, False)
    assert body["pickup"]["scannedCount"] == 1
    bag = store.bags[world["codes"][0]]
    assert bag.status == BagStatus.COLLECTED
    assert bag.collectorUid == "col-1"
    assert store.routes[world["pid"]].scannedCount == 1


def test_repeated_scan_succeeds_without_changes(
    client: TestClient, world: dict, store: FakeDataStore
) -> None:
    accept(client, world)
    scan(client, world, world["codes"][0])
    before = (store.commits, store.bags[world["codes"][0]])
    response = scan(client, world, world["codes"][0])
    assert response.status_code == 200
    assert response.json()["alreadyScanned"] is True
    assert (store.commits, store.bags[world["codes"][0]]) == before


def test_scan_bag_from_another_pickup(client: TestClient, world: dict, identity: FakeIdentity) -> None:
    other = onboard(client, identity, "res-2")
    other_code = other["bags"][0]["code"]
    body = {"date": TOMORROW, "timeSlot": "morning", "bagCodes": [other_code]}
    client.post("/pickups", json=body, headers=other["headers"])
    accept(client, world)
    response = scan(client, world, other_code)
    assert response.status_code == 409
    assert detail(response) == "wrong_pickup"


def test_scan_households_bag_not_in_this_pickup(client: TestClient, world: dict) -> None:
    accept(client, world)
    response = scan(client, world, world["codes"][4])  # issued, never scheduled
    assert response.status_code == 409
    assert detail(response) == "wrong_pickup"


def test_scan_unknown_but_valid_code(client: TestClient, world: dict) -> None:
    accept(client, world)
    response = scan(client, world, generate_code())
    assert response.status_code == 404
    assert detail(response) == "unknown_code"


def test_scan_typo_is_caught_by_check_character(client: TestClient, world: dict) -> None:
    accept(client, world)
    code = world["codes"][0]
    typo = code[:-1] + ("A" if code[-1] != "A" else "B")
    response = scan(client, world, typo)
    assert response.status_code == 422
    assert detail(response) == "invalid_code"
    assert scan(client, world, "hello").status_code == 422


def test_scan_requires_accepted_pickup(client: TestClient, world: dict) -> None:
    assert scan(client, world, world["codes"][0]).status_code == 404
    accept(client, world)
    assert scan(client, world, world["codes"][0], "rival").status_code == 404


def test_scan_after_completion_is_rejected(client: TestClient, world: dict) -> None:
    accept(client, world)
    for code in world["codes"][:3]:
        scan(client, world, code)
    client.post(f"/collector/pickups/{world['pid']}/complete", json={}, headers=world["col"])
    response = scan(client, world, world["codes"][0])
    assert response.status_code == 409
    assert detail(response) == "pickup_not_active"


def test_resident_sees_collected_bags(client: TestClient, world: dict) -> None:
    accept(client, world)
    scan(client, world, world["codes"][0])
    bags = {b["code"]: b["status"] for b in client.get("/bags/mine", headers=world["home"]["headers"]).json()}
    assert bags[world["codes"][0]] == "collected"


def test_resident_cannot_cancel_after_a_scan(client: TestClient, world: dict) -> None:
    accept(client, world)
    scan(client, world, world["codes"][0])
    response = client.post(f"/pickups/{world['pid']}/cancel", headers=world["home"]["headers"])
    assert response.status_code == 409


def test_resident_cancel_of_assigned_pickup_updates_route(
    client: TestClient, world: dict, store: FakeDataStore
) -> None:
    accept(client, world)
    client.post(f"/pickups/{world['pid']}/cancel", headers=world["home"]["headers"])
    assert store.routes[world["pid"]].status == PickupStatus.CANCELLED


# --- simulate scan (demo only) ---


def test_simulate_scan_for_demo_collector(
    client: TestClient, world: dict, identity: FakeIdentity, users: FakeUserStore, store: FakeDataStore
) -> None:
    world["demo"] = make_collector(identity, users, "demo-collector", ["colombo-05"])
    accept(client, world, "demo")
    url = f"/collector/pickups/{world['pid']}/simulate-scan"
    response = client.post(url, json={"slot": 2}, headers=world["demo"])
    assert response.status_code == 200
    assert response.json()["code"] == world["codes"][1]
    assert store.bags[world["codes"][1]].status == BagStatus.COLLECTED
    assert client.post(url, json={"slot": 4}, headers=world["demo"]).status_code == 422


def test_simulate_scan_forbidden_for_real_collectors(client: TestClient, world: dict) -> None:
    accept(client, world)
    url = f"/collector/pickups/{world['pid']}/simulate-scan"
    response = client.post(url, json={"slot": 1}, headers=world["col"])
    assert response.status_code == 403
    assert detail(response) == "demo_only"


def test_me_reports_demo_flag(client: TestClient, world: dict, identity: FakeIdentity, users: FakeUserStore) -> None:
    demo = make_collector(identity, users, "demo-collector", ["colombo-07"])
    me = client.get("/me", headers=demo).json()
    assert me["isDemo"] is True
    assert me["zones"] == ["colombo-07"]
    assert client.get("/me", headers=world["col"]).json()["isDemo"] is False


# --- complete ---


def complete(client: TestClient, w: dict, reason: str | None = None):  # noqa: ANN201
    body = {"missingReason": reason} if reason is not None else {}
    return client.post(f"/collector/pickups/{w['pid']}/complete", json=body, headers=w["col"])


def test_complete_with_all_bags(client: TestClient, world: dict, store: FakeDataStore) -> None:
    accept(client, world)
    for code in world["codes"][:3]:
        scan(client, world, code)
    response = complete(client, world)
    assert response.status_code == 200
    assert response.json()["status"] == "collected"
    pickup = store.pickups[world["pid"]]
    assert pickup.collectedAt is not None and pickup.missingBagsReason is None
    assert store.routes[world["pid"]].status == PickupStatus.COLLECTED


def test_partial_complete_requires_reason(client: TestClient, world: dict) -> None:
    accept(client, world)
    scan(client, world, world["codes"][0])
    response = complete(client, world)
    assert response.status_code == 422
    assert detail(response) == "missing_reason_required"
    assert complete(client, world, "   ").status_code == 422


def test_partial_complete_releases_unscanned_bags(
    client: TestClient, world: dict, store: FakeDataStore
) -> None:
    accept(client, world)
    scan(client, world, world["codes"][0])
    response = complete(client, world, "Only one bag at the gate")
    assert response.status_code == 200
    body = response.json()
    assert body["missingBagsReason"] == "Only one bag at the gate"
    assert body["bagCount"] == 1
    assert [s["status"] for s in body["slots"]] == ["collected", "released", "released"]
    for code in world["codes"][1:3]:
        assert store.bags[code].status == BagStatus.ISSUED
        assert store.bags[code].pickupId is None
    assert store.routes[world["pid"]].bagCount == 1


def test_complete_with_nothing_scanned_is_rejected(client: TestClient, world: dict) -> None:
    accept(client, world)
    response = complete(client, world, "nobody home")
    assert response.status_code == 409
    assert detail(response) == "nothing_scanned"


def test_complete_requires_assignment(client: TestClient, world: dict) -> None:
    assert complete(client, world).status_code == 404


# --- missed ---


def missed(client: TestClient, w: dict, reason: str):  # noqa: ANN201
    return client.post(f"/collector/pickups/{w['pid']}/missed", json={"reason": reason}, headers=w["col"])


def test_missed_releases_all_bags(client: TestClient, world: dict, store: FakeDataStore) -> None:
    accept(client, world)
    response = missed(client, world, "No one answered")
    assert response.status_code == 200
    assert response.json()["status"] == "missed"
    assert store.pickups[world["pid"]].missedReason == "No one answered"
    for code in world["codes"][:3]:
        assert store.bags[code].status == BagStatus.ISSUED
        assert store.bags[code].pickupId is None
    assert store.routes[world["pid"]].status == PickupStatus.MISSED


def test_missed_requires_reason(client: TestClient, world: dict) -> None:
    accept(client, world)
    assert missed(client, world, "").status_code == 422
    assert missed(client, world, "   ").status_code == 422


def test_missed_after_scan_is_rejected(client: TestClient, world: dict) -> None:
    accept(client, world)
    scan(client, world, world["codes"][0])
    response = missed(client, world, "changed my mind")
    assert response.status_code == 409
    assert detail(response) == "bags_already_scanned"


def test_missed_pickup_lets_resident_rebook_same_date(client: TestClient, world: dict) -> None:
    accept(client, world)
    missed(client, world, "No one home")
    body = {"date": TOMORROW, "timeSlot": "morning", "bagCodes": world["codes"][:2]}
    assert client.post("/pickups", json=body, headers=world["home"]["headers"]).status_code == 201


def test_terminal_pickups_cannot_be_missed_or_completed(client: TestClient, world: dict) -> None:
    accept(client, world)
    missed(client, world, "No one home")
    assert missed(client, world, "again").status_code == 409
    assert complete(client, world).status_code == 409


# --- handover ---


def collect(client: TestClient, w: dict, codes: list[str], reason: str | None = None) -> None:
    accept(client, w)
    for code in codes:
        assert scan(client, w, code).status_code == 200
    assert complete(client, w, reason).status_code == 200


def handover_scan(client: TestClient, w: dict, code: str, who: str = "col"):  # noqa: ANN201
    return client.post("/collector/handover/scan", json={"code": code}, headers=w[who])


def test_handover_lists_bags_in_my_van(client: TestClient, world: dict) -> None:
    collect(client, world, world["codes"][:3])
    van = client.get("/collector/handover", headers=world["col"]).json()
    assert len(van) == 1
    assert van[0]["pickupId"] == world["pid"]
    assert van[0]["householdName"] == HOUSEHOLD["name"]
    assert [b["code"] for b in van[0]["bags"]] == world["codes"][:3]
    assert client.get("/collector/handover", headers=world["rival"]).json() == []


def test_handover_completes_pickup_when_all_bags_arrive(
    client: TestClient, world: dict, store: FakeDataStore
) -> None:
    collect(client, world, world["codes"][:3])
    for i, code in enumerate(world["codes"][:3]):
        body = handover_scan(client, world, code).json()
        assert body["alreadyScanned"] is False
        assert body["pickupDelivered"] is (i == 2)
        assert store.bags[code].status == BagStatus.AT_WAREHOUSE
    pickup = store.pickups[world["pid"]]
    assert pickup.status == PickupStatus.DELIVERED
    assert pickup.deliveredAt is not None
    assert store.routes[world["pid"]].status == PickupStatus.DELIVERED
    assert client.get("/collector/handover", headers=world["col"]).json() == []
    resident_view = client.get("/pickups/mine", headers=world["home"]["headers"]).json()
    assert [e["status"] for e in resident_view[0]["statusHistory"]] == [
        "requested", "assigned", "collected", "delivered"
    ]


def test_handover_after_partial_counts_only_collected_bags(
    client: TestClient, world: dict, store: FakeDataStore
) -> None:
    collect(client, world, world["codes"][:1], "Two bags missing")
    assert handover_scan(client, world, world["codes"][0]).json()["pickupDelivered"] is True
    assert store.pickups[world["pid"]].status == PickupStatus.DELIVERED


def test_repeated_handover_scan_is_noop(client: TestClient, world: dict, store: FakeDataStore) -> None:
    collect(client, world, world["codes"][:3])
    handover_scan(client, world, world["codes"][0])
    commits = store.commits
    body = handover_scan(client, world, world["codes"][0]).json()
    assert body["alreadyScanned"] is True
    assert store.commits == commits


def test_handover_rejects_bags_not_in_my_van(client: TestClient, world: dict) -> None:
    accept(client, world)
    scan(client, world, world["codes"][0])
    # Collected but the pickup isn't completed yet -> still at the door, not handed over.
    assert detail(handover_scan(client, world, world["codes"][0])) == "not_in_your_van"
    complete(client, world, "rest missing")
    assert detail(handover_scan(client, world, world["codes"][0], "rival")) == "not_in_your_van"
    assert detail(handover_scan(client, world, world["codes"][1])) == "not_in_your_van"
    assert handover_scan(client, world, generate_code()).status_code == 404
    assert handover_scan(client, world, "ECO-XXXX-XX").status_code == 422


# --- demo collector data ---


def test_demo_collector_gets_one_fresh_pickup_today() -> None:
    store, users, clock = FakeDataStore(), FakeUserStore(), FixedClock()
    users.upsert("demo-collector", "Demo Collector", None, Role.COLLECTOR)
    first = ensure_demo_collector_data(store, users, clock)
    assert first is not None
    pickup = store.pickups[first]
    assert (pickup.date, pickup.status, pickup.zone) == ("2026-03-10", PickupStatus.REQUESTED, "colombo-07")
    assert pickup.timeSlot == "morning"  # 09:00 in Colombo
    assert len(pickup.bagCodes) == 2
    assert users.docs["demo-collector"].zones == ["colombo-07", "colombo-03", "colombo-05"]
    # Bounded: nothing new while a requested pickup is still available today.
    count = len(store.pickups)
    assert ensure_demo_collector_data(store, users, clock) is None
    assert len(store.pickups) == count


def test_demo_collector_gets_a_new_one_after_accepting(client: TestClient, store: FakeDataStore) -> None:
    token = client.post("/auth/demo/collector").json()["token"]
    assert token == "custom-token-for-demo-collector"
    today = [p for p in store.pickups.values() if p.date == "2026-03-10"]
    assert len(today) == 1
    store.pickups[today[0].id] = today[0].model_copy(update={"status": PickupStatus.ASSIGNED})
    client.post("/auth/demo/collector")
    today = [p for p in store.pickups.values() if p.date == "2026-03-10"]
    assert len(today) == 2
    assert sum(p.status == PickupStatus.REQUESTED for p in today) == 1
