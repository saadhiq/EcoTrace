"""Warehouse operator: queue, analyze (mocked Gemini), confirm, transitions."""

from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.ai.classifier import AiError
from app.demo import ensure_demo_operator_data
from app.models import BagStatus, PickupStatus
from tests.fakes import FakeClassifier, FakeDataStore, FakeIdentity, FakePhotoStore, FakeUserStore, FixedClock
from tests.helpers import HOUSEHOLD, auth, onboard
from tests.test_collector import make_collector

JPEG = b"\xff\xd8\xff\xe0" + b"0" * 2000
PNG = b"\x89PNG\r\n\x1a\n" + b"0" * 2000


@pytest.fixture
def warehouse(client: TestClient, identity: FakeIdentity, users: FakeUserStore) -> dict[str, Any]:
    """A pickup with 2 bags that has been collected and handed over (delivered)."""
    home = onboard(client, identity, "res-1")
    codes = [b["code"] for b in home["bags"]][:2]
    pickup = client.post(
        "/pickups", json={"date": "2026-03-11", "timeSlot": "morning", "bagCodes": codes}, headers=home["headers"]
    ).json()
    col = make_collector(identity, users, "col-1", ["colombo-05"])
    base = f"/collector/pickups/{pickup['id']}"
    assert client.post(f"{base}/accept", headers=col).status_code == 200
    for code in codes:
        assert client.post(f"{base}/scan", json={"code": code}, headers=col).status_code == 200
    assert client.post(f"{base}/complete", json={}, headers=col).status_code == 200
    for code in codes:
        assert client.post("/collector/handover/scan", json={"code": code}, headers=col).status_code == 200
    identity.issue("tok-op", "op-1", role="operator")
    return {"home": home, "codes": codes, "pid": pickup["id"], "op": auth("tok-op"), "col": col}


def analyze(client: TestClient, w: dict, code: str, files: list[tuple[str, bytes, str]] | None = None):  # noqa: ANN201
    files = files or [("bag.jpg", JPEG, "image/jpeg")]
    return client.post(
        f"/operator/bags/{code}/analyze",
        files=[("photos", f) for f in files],
        headers=w["op"],
    )


def ai_items(classifier: FakeClassifier) -> list[dict[str, Any]]:
    """Final items exactly as the AI returned them (no edits)."""
    return [
        {**item.model_dump(exclude={"confidence"}), "aiIndex": i}
        for i, item in enumerate(classifier.result.items)
    ]


def confirm(client: TestClient, w: dict, code: str, items: list[dict], quality: str = "mixed", hazards=None):  # noqa: ANN001, ANN201
    body = {"finalItems": items, "segregationQuality": quality, "hazardFlags": hazards or []}
    return client.post(f"/operator/bags/{code}/confirm", json=body, headers=w["op"])


def detail(response) -> str:  # noqa: ANN001
    return response.json()["detail"]


# --- queue ---


def test_queue_lists_bags_at_warehouse_without_pii(
    client: TestClient, warehouse: dict, clock: FixedClock
) -> None:
    response = client.get("/operator/queue", headers=warehouse["op"])
    assert response.status_code == 200
    queue = response.json()
    assert {q["code"] for q in queue} == set(warehouse["codes"])
    assert queue[0]["zone"] == "colombo-05"
    assert queue[0]["pickupDate"] == "2026-03-11"
    assert queue[0]["hasDraft"] is False
    text = str(queue)
    for pii in (HOUSEHOLD["name"], HOUSEHOLD["phone"], HOUSEHOLD["addressLine"]):
        assert pii not in text


def test_queue_is_oldest_first(client: TestClient, warehouse: dict, store: FakeDataStore) -> None:
    first, second = warehouse["codes"]
    bag = store.bags[second]
    history = list(bag.statusHistory)
    history[-1] = history[-1].model_copy(update={"at": history[-1].at.replace(year=2025)})
    store.bags[second] = bag.model_copy(update={"statusHistory": history})
    codes = [q["code"] for q in client.get("/operator/queue", headers=warehouse["op"]).json()]
    assert codes == [second, first]


def test_operator_endpoints_require_operator_role(client: TestClient, warehouse: dict) -> None:
    assert client.get("/operator/queue", headers=warehouse["col"]).status_code == 403
    assert client.get("/operator/queue", headers=warehouse["home"]["headers"]).status_code == 403
    assert client.get("/operator/queue").status_code == 401


def test_taxonomy_is_public(client: TestClient) -> None:
    body = client.get("/taxonomy").json()
    assert [c["id"] for c in body["categories"]] == [
        "plastic", "paper_cardboard", "glass", "metal", "organic", "e_waste", "textile", "hazardous", "other"
    ]
    assert body["segregationQualities"] == ["good", "mixed", "poor"]


# --- analyze ---


def test_analyze_returns_result_and_saves_draft(
    client: TestClient, warehouse: dict, store: FakeDataStore, classifier: FakeClassifier, photo_store: FakePhotoStore
) -> None:
    code = warehouse["codes"][0]
    response = analyze(client, warehouse, code, [("a.jpg", JPEG, "image/jpeg"), ("b.png", PNG, "image/png")])
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["model"] == "fake-gemini"
    assert body["latencyMs"] == 1234
    assert body["tokenUsage"]["total"] == 1450
    assert body["photoCount"] == 2
    assert len(body["result"]["items"]) == 3
    assert [mime for _, mime in classifier.calls[0]] == ["image/jpeg", "image/png"]
    record = store.records[code]
    assert record.status == "draft"
    assert record.aiResult is not None and len(record.photoPaths) == 2
    assert store.bags[code].status == BagStatus.AT_WAREHOUSE  # not processed yet
    queue = client.get("/operator/queue", headers=warehouse["op"]).json()
    assert {q["code"]: q["hasDraft"] for q in queue}[code] is True


def test_reanalyze_keeps_all_photo_paths(client: TestClient, warehouse: dict, store: FakeDataStore) -> None:
    code = warehouse["codes"][0]
    analyze(client, warehouse, code)
    analyze(client, warehouse, code)
    assert len(store.records[code].photoPaths) == 2


@pytest.mark.parametrize(
    "files,status,code_",
    [
        ([("a.gif", b"GIF89a" + b"0" * 100, "image/gif")], 415, "unsupported_photo_type"),
        ([("a.jpg", b"not really a jpeg", "image/jpeg")], 415, "unsupported_photo_type"),
        ([("a.jpg", JPEG, "image/jpeg")] * 4, 422, "photo_count"),
        ([("big.jpg", b"\xff\xd8\xff" + b"0" * (4 * 1024 * 1024), "image/jpeg")], 413, "photo_too_large"),
    ],
)
def test_analyze_validates_photos(client: TestClient, warehouse: dict, classifier: FakeClassifier,
                                  files: list, status: int, code_: str) -> None:
    response = analyze(client, warehouse, warehouse["codes"][0], files)
    assert response.status_code == status
    assert detail(response) == code_
    assert classifier.calls == []


def test_analyze_requires_bag_at_warehouse(client: TestClient, warehouse: dict) -> None:
    other = warehouse["home"]["bags"][4]["code"]  # still issued
    assert detail(analyze(client, warehouse, other)) == "not_at_warehouse"
    assert analyze(client, warehouse, "ECO-2222-22").status_code == 404


def test_gemini_timeout_gives_manual_fallback(
    client: TestClient, warehouse: dict, store: FakeDataStore, classifier: FakeClassifier
) -> None:
    classifier.error = AiError("unavailable", "timeout")
    code = warehouse["codes"][0]
    response = analyze(client, warehouse, code)
    assert response.status_code == 504
    assert detail(response) == "ai_unavailable"
    draft = store.records[code]
    assert draft.aiError == "unavailable" and draft.aiResult is None
    assert len(draft.photoPaths) == 1  # photos kept for later review
    # Operator enters items by hand.
    items = [{"name": "glass jar", "category": "glass", "quantity": 1, "recyclable": True}]
    done = confirm(client, warehouse, code, items, "good")
    assert done.status_code == 200, done.text
    record = done.json()["record"]
    assert record["source"] == "manual"
    assert record["edited"] is True
    assert record["aiResult"] is None
    assert record["aiError"] == "unavailable"
    assert record["photoPaths"] == draft.photoPaths


def test_gemini_invalid_output_is_502(client: TestClient, warehouse: dict, classifier: FakeClassifier) -> None:
    classifier.error = AiError("invalid_output", "garbage")
    response = analyze(client, warehouse, warehouse["codes"][0])
    assert (response.status_code, detail(response)) == (502, "ai_invalid_output")


def test_photo_storage_failure_is_503(client: TestClient, warehouse: dict, photo_store: FakePhotoStore,
                                      classifier: FakeClassifier) -> None:
    photo_store.fail = True
    response = analyze(client, warehouse, warehouse["codes"][0])
    assert (response.status_code, detail(response)) == (503, "photo_upload_failed")
    assert classifier.calls == []


def test_analyze_is_rate_limited_per_operator(client: TestClient, warehouse: dict) -> None:
    statuses = [analyze(client, warehouse, warehouse["codes"][0]).status_code for _ in range(6)]
    assert statuses == [200] * 5 + [429]


# --- confirm ---


def test_confirm_without_edits(
    client: TestClient, warehouse: dict, store: FakeDataStore, classifier: FakeClassifier
) -> None:
    code = warehouse["codes"][0]
    analyze(client, warehouse, code)
    response = confirm(client, warehouse, code, ai_items(classifier), "mixed")
    assert response.status_code == 200, response.text
    record = response.json()["record"]
    assert (record["edited"], record["editCount"], record["source"]) == (False, 0, "ai")
    assert record["status"] == "confirmed"
    assert record["operatorUid"] == "op-1"
    assert record["model"] == "fake-gemini" and record["latencyMs"] == 1234
    assert len(record["aiResult"]["items"]) == 3 and len(record["finalItems"]) == 3
    assert "aiIndex" not in record["finalItems"][0]
    assert store.bags[code].status == BagStatus.PROCESSED
    assert response.json()["pickupProcessed"] is False  # one bag still waiting
    assert store.pickups[warehouse["pid"]].status == PickupStatus.DELIVERED


def test_confirm_with_edits_counts_changes(client: TestClient, warehouse: dict, classifier: FakeClassifier) -> None:
    code = warehouse["codes"][0]
    analyze(client, warehouse, code)
    items = ai_items(classifier)
    items[0]["quantity"] = 4  # modified
    del items[2]  # removed (the low-confidence wrapper)
    items.append({"name": "glass bottle", "category": "glass", "quantity": 1, "recyclable": True})  # added
    response = confirm(client, warehouse, code, items, "poor", ["broken_glass"])  # +quality +hazards
    record = response.json()["record"]
    assert record["edited"] is True
    assert record["editCount"] == 5
    assert record["source"] == "ai_edited"
    assert record["hazardFlags"] == ["broken_glass"]
    assert record["aiResult"]["segregationQuality"] == "mixed"  # AI output kept intact


def test_renaming_an_item_counts_as_one_edit(client: TestClient, warehouse: dict, classifier: FakeClassifier) -> None:
    code = warehouse["codes"][0]
    analyze(client, warehouse, code)
    items = ai_items(classifier)
    items[1]["name"] = "Aluminium Can"  # case-only change is not an edit
    items[2]["name"] = "chips packet"
    assert confirm(client, warehouse, code, items).json()["record"]["editCount"] == 1


def test_last_bag_marks_pickup_processed(
    client: TestClient, warehouse: dict, store: FakeDataStore, classifier: FakeClassifier
) -> None:
    first, last = warehouse["codes"]
    analyze(client, warehouse, first)
    confirm(client, warehouse, first, ai_items(classifier))
    response = confirm(client, warehouse, last, [{"name": "can", "category": "metal", "quantity": 1}], "good")
    assert response.json()["pickupProcessed"] is True
    assert store.pickups[warehouse["pid"]].status == PickupStatus.PROCESSED
    assert store.routes[warehouse["pid"]].status == PickupStatus.PROCESSED
    mine = client.get("/pickups/mine", headers=warehouse["home"]["headers"]).json()
    assert [e["status"] for e in mine[0]["statusHistory"]][-2:] == ["delivered", "processed"]
    assert client.get("/operator/queue", headers=warehouse["op"]).json() == []


def test_confirm_twice_is_rejected(client: TestClient, warehouse: dict, classifier: FakeClassifier) -> None:
    code = warehouse["codes"][0]
    analyze(client, warehouse, code)
    confirm(client, warehouse, code, ai_items(classifier))
    response = confirm(client, warehouse, code, ai_items(classifier))
    assert (response.status_code, detail(response)) == (409, "already_processed")


def test_confirm_validation(client: TestClient, warehouse: dict, classifier: FakeClassifier) -> None:
    code = warehouse["codes"][0]
    analyze(client, warehouse, code)
    assert confirm(client, warehouse, code, []).status_code == 422
    bad_category = [{"name": "thing", "category": "unobtainium", "quantity": 1}]
    assert confirm(client, warehouse, code, bad_category).status_code == 422
    assert confirm(client, warehouse, code, [{"name": "", "category": "other"}]).status_code == 422
    bad_index = [{**ai_items(classifier)[0], "aiIndex": 9}]
    assert detail(confirm(client, warehouse, code, bad_index)) == "invalid_ai_index"
    dup = [ai_items(classifier)[0], ai_items(classifier)[0]]
    assert detail(confirm(client, warehouse, code, dup)) == "invalid_ai_index"
    assert confirm(client, warehouse, code, ai_items(classifier), "great").status_code == 422
    assert confirm(client, warehouse, code, ai_items(classifier), "good", ["radioactive"]).status_code == 422


def test_get_bag_shows_draft_and_progress(client: TestClient, warehouse: dict, classifier: FakeClassifier) -> None:
    code = warehouse["codes"][0]
    analyze(client, warehouse, code)
    view = client.get(f"/operator/bags/{code.lower()}", headers=warehouse["op"]).json()
    assert view["status"] == "at_warehouse"
    assert view["record"]["status"] == "draft"
    assert (view["bagsInPickup"], view["processedInPickup"]) == (2, 0)


# --- demo operator data ---


def test_demo_operator_queue_is_seeded_once() -> None:
    store, clock = FakeDataStore(), FixedClock()
    pid = ensure_demo_operator_data(store, clock)
    assert pid is not None
    pickup = store.pickups[pid]
    assert pickup.status == PickupStatus.DELIVERED
    assert pickup.collectorUid == "demo-collector"
    assert [e.status for e in pickup.statusHistory] == ["requested", "assigned", "collected", "delivered"]
    waiting = store.list_bags_by_status(BagStatus.AT_WAREHOUSE)
    assert len(waiting) == 2
    assert all([e.status for e in b.statusHistory] == ["issued", "scheduled", "collected", "at_warehouse"]
               for b in waiting)
    assert store.routes[pid].status == PickupStatus.DELIVERED
    assert ensure_demo_operator_data(store, clock) is None  # queue not empty -> nothing new


def test_demo_operator_login_seeds_queue(client: TestClient, store: FakeDataStore) -> None:
    assert client.post("/auth/demo/operator").status_code == 200
    assert len(store.list_bags_by_status(BagStatus.AT_WAREHOUSE)) == 2
    client.post("/auth/demo/operator")
    assert len(store.list_bags_by_status(BagStatus.AT_WAREHOUSE)) == 2
