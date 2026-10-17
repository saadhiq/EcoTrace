"""Admin: demo guard, overview, AI quality, pickups + reassign, people, partners, demo keys, cache."""

from datetime import UTC, datetime
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.admin import TTLCache, ai_quality, p95
from app.demo_partners import ensure_synthetic_collector, ensure_synthetic_households, upsert_partner
from app.models import AiItem, AiResult, BagStatus, PickupStatus, Role, WasteItem, WasteRecord
from app.secrets import SecretManagerDemoKeyReader
from tests.fakes import FakeDataStore, FakeIdentity, FakeUserStore, FixedClock
from tests.helpers import auth, onboard
from tests.test_collector import make_collector

NOW = datetime(2026, 3, 10, tzinfo=UTC)


@pytest.fixture
def admins(identity: FakeIdentity, users: FakeUserStore) -> dict[str, dict[str, str]]:
    identity.issue("tok-demo-admin", "demo-admin", role="admin")
    identity.issue("tok-real-admin", "adm-1", role="admin")
    return {"demo": auth("tok-demo-admin"), "real": auth("tok-real-admin")}


@pytest.fixture
def world(client: TestClient, identity: FakeIdentity, users: FakeUserStore, store: FakeDataStore,
          clock: FixedClock, admins: dict) -> dict[str, Any]:
    """A real household pickup + a synthetic-household pickup, two collectors covering colombo-05."""
    real = onboard(client, identity, "res-1")  # zone colombo-05
    codes = [b["code"] for b in real["bags"]][:2]
    p_real = client.post("/pickups", json={"date": "2026-03-11", "timeSlot": "morning", "bagCodes": codes},
                         headers=real["headers"]).json()
    col = make_collector(identity, users, "col-1", ["colombo-05", "colombo-07"])
    ensure_synthetic_collector(users)
    # A pickup belonging to a synthetic household (allowed for the demo admin).
    synth_home = onboard(client, identity, "synthetic-hh-99")
    store.households["synthetic-hh-99"] = store.households["synthetic-hh-99"].model_copy(update={"isSynthetic": True})
    p_syn = client.post("/pickups", json={"date": "2026-03-11", "timeSlot": "afternoon",
                                          "bagCodes": [synth_home["bags"][0]["code"]]}, headers=synth_home["headers"]).json()
    return {"pid": p_real["id"], "syn": p_syn["id"], "col": col, "codes": codes, **admins}


# --- demo guard ---

PROTECTED = [
    ("post", "/admin/staff", {"email": "new@example.com", "name": "New", "role": "collector", "zones": ["colombo-05"]}),
    ("patch", "/admin/users/col-1/zones", {"zones": ["colombo-07"]}),
    ("post", "/admin/partners", {"name": "Real Partner"}),
    ("post", "/admin/partners/greencart-lk/rotate-key", None),
]


@pytest.mark.parametrize("method,url,body", PROTECTED)
def test_demo_admin_is_blocked_from_every_protected_action(
    client: TestClient, world: dict, method: str, url: str, body: dict | None
) -> None:
    response = getattr(client, method)(url, json=body, headers=world["demo"]) if body is not None \
        else getattr(client, method)(url, headers=world["demo"])
    assert response.status_code == 403
    assert response.json()["detail"] == "demo_disabled"


@pytest.mark.parametrize("method,url,body", PROTECTED)
def test_real_admin_passes_the_guard(
    client: TestClient, world: dict, store: FakeDataStore, clock: FixedClock, method: str, url: str, body: dict | None
) -> None:
    upsert_partner(store, clock, "greencart-lk", rotate_key=False)
    response = getattr(client, method)(url, json=body, headers=world["real"]) if body is not None \
        else getattr(client, method)(url, headers=world["real"])
    assert response.status_code != 403, response.text


def test_demo_admin_can_view_everything(client: TestClient, world: dict, store: FakeDataStore, clock: FixedClock) -> None:
    upsert_partner(store, clock, "greencart-lk", rotate_key=False)
    for url in ["/admin/overview", "/admin/overview?range=30d&synthetic=exclude", "/admin/ai-quality",
                "/admin/pickups?date=2026-03-11", f"/admin/pickups/{world['pid']}", "/admin/users",
                "/admin/users?role=collector", "/admin/partners", "/admin/partners/greencart-lk/demo-key"]:
        assert client.get(url, headers=world["demo"]).status_code == 200, url


def test_non_admins_are_rejected(client: TestClient, world: dict, identity: FakeIdentity) -> None:
    identity.issue("tok-op", "op-1", role="operator")
    assert client.get("/admin/overview", headers=auth("tok-op")).status_code == 403
    assert client.get("/admin/overview").status_code == 401


# --- assign / reassign ---


def assign(client: TestClient, pid: str, collector: str, headers: dict):  # noqa: ANN201
    return client.post(f"/admin/pickups/{pid}/assign", json={"collectorUid": collector}, headers=headers)


def test_demo_admin_may_only_reassign_demo_or_synthetic_pickups(client: TestClient, world: dict) -> None:
    blocked = assign(client, world["pid"], "col-1", world["demo"])
    assert blocked.status_code == 403 and blocked.json()["detail"] == "demo_disabled"
    allowed = assign(client, world["syn"], "col-1", world["demo"])
    assert allowed.status_code == 200
    assert allowed.json()["pickup"]["status"] == "assigned"


def test_assign_uses_state_machine_and_moves_route_mirror(
    client: TestClient, world: dict, store: FakeDataStore
) -> None:
    pid = world["pid"]
    body = assign(client, pid, "col-1", world["real"]).json()
    assert body["pickup"]["collectorUid"] == "col-1" and body["pickup"]["status"] == "assigned"
    assert [e["status"] for e in body["timeline"] if e["kind"] == "pickup"] == ["requested", "assigned"]
    assert store.routes[pid].collectorUid == "col-1"
    # Reassign to collector B (still before any scan).
    body = assign(client, pid, "synthetic-collector-b", world["real"]).json()
    assert body["pickup"]["collectorUid"] == "synthetic-collector-b" and body["pickup"]["status"] == "assigned"
    assert store.routes[pid].collectorUid == "synthetic-collector-b"
    assert [e["status"] for e in body["timeline"] if e["kind"] == "pickup"][-1] == "assigned"
    assert assign(client, pid, "synthetic-collector-b", world["real"]).json()["detail"] == "already_assigned"


def test_reassign_blocked_after_a_scan(client: TestClient, world: dict, store: FakeDataStore) -> None:
    pid = world["pid"]
    assign(client, pid, "col-1", world["real"])
    code = world["codes"][0]
    store.bags[code] = store.bags[code].model_copy(update={"status": BagStatus.COLLECTED})
    response = assign(client, pid, "synthetic-collector-b", world["real"])
    assert response.status_code == 409 and response.json()["detail"] == "not_reassignable"
    assert client.get(f"/admin/pickups/{pid}", headers=world["real"]).json()["canReassign"] is False


def test_assign_validates_collector_and_zone(client: TestClient, world: dict, identity: FakeIdentity,
                                             users: FakeUserStore, store: FakeDataStore) -> None:
    make_collector(identity, users, "col-far", ["nugegoda"])
    assert assign(client, world["pid"], "col-far", world["real"]).json()["detail"] == "outside_collector_zones"
    assert assign(client, world["pid"], "res-1", world["real"]).json()["detail"] == "not_a_collector"
    assert assign(client, "nope", "col-1", world["real"]).status_code == 404
    store.pickups[world["pid"]] = store.pickups[world["pid"]].model_copy(update={"status": PickupStatus.CANCELLED})
    assert assign(client, world["pid"], "col-1", world["real"]).status_code == 409


def test_pickup_list_filters_and_pagination(client: TestClient, world: dict) -> None:
    page = client.get("/admin/pickups?date=2026-03-11&pageSize=1", headers=world["demo"]).json()
    assert page["total"] == 2 and len(page["items"]) == 1 and page["items"][0]["timeSlot"] == "morning"
    page2 = client.get("/admin/pickups?date=2026-03-11&pageSize=1&page=2", headers=world["demo"]).json()
    assert page2["items"][0]["isDemo"] is True
    assert client.get("/admin/pickups?date=2026-03-11&status=assigned", headers=world["demo"]).json()["total"] == 0
    assert client.get("/admin/pickups?date=2026-03-11&zone=mars", headers=world["demo"]).status_code == 422


# --- AI quality ---


def record(code: str, *, edited: bool = False, edits: int = 0, latency: int | None = 1000, ai: bool = True,
           confidences: tuple[float, ...] = (0.9, 0.9), source: str | None = None, synthetic: bool = False,
           added: int | None = 0, removed: int | None = 0, ai_error: str | None = None) -> WasteRecord:
    ai_result = AiResult(items=[AiItem(name=f"i{n}", category="plastic", confidence=c) for n, c in enumerate(confidences)],
                         segregationQuality="mixed") if ai else None
    return WasteRecord(
        bagCode=code, householdId="h", pickupId="p", status="confirmed", aiResult=ai_result, edited=edited or not ai,
        editCount=edits, latencyMs=latency if ai else None, source=source or ("ai_edited" if edited else ("ai" if ai else "manual")),
        finalItems=[WasteItem(name="x", category="plastic")], isSynthetic=synthetic, model="gemini-3.5-flash" if ai else None,
        itemsAdded=added, itemsRemoved=removed, itemsModified=0, aiError=ai_error, processedAt=NOW,
    )


def test_p95_nearest_rank() -> None:
    assert p95([]) is None
    assert p95([500]) == 500
    assert p95(list(range(1, 101))) == 95
    assert p95([100, 200, 300, 400, 5000]) == 5000  # ceil(0.95*5)=5th value


def test_ai_quality_calculations() -> None:
    records = [
        record("a", latency=1000),
        record("b", edited=True, edits=2, latency=2000, added=1, removed=1),
        record("c", edited=True, edits=1, latency=3000, confidences=(0.4, 0.9)),
        record("d", latency=10_000, confidences=(0.5, 0.55)),
        record("m", ai=False, ai_error="unavailable"),  # manual fallback after a failure
        record("s", edited=True, edits=9, latency=1, synthetic=True),  # excluded
        record("old", edited=True, edits=1, latency=1500, added=None, removed=None),  # pre-breakdown record
    ]
    drafts = [record("draft-fail", ai=False, ai_error="unavailable").model_copy(update={"status": "draft"})]
    q = ai_quality(records, drafts)
    assert (q.recordsConsidered, q.bagsAnalyzed) == (6, 5)
    assert q.correctionRate == 0.6  # b, c, old edited of 5 analyzed
    assert q.avgCorrectionsPerBag == 0.8  # (0+2+1+0+1)/5
    assert q.avgLatencyMs == 3500.0 and q.p95LatencyMs == 10_000
    assert q.manualFallbacks == 1 and q.failures == 2  # the manual record's aiError + the failed draft
    assert q.lowConfidenceShare == 0.3  # 3 of 10 AI items below 0.6
    assert (q.itemsAdded, q.itemsRemoved, q.estimatedEditRecords) == (1, 2, 1)  # 'old': 1 final vs 2 AI -> 1 removed
    assert q.models == {"gemini-3.5-flash": 5}


def test_ai_quality_endpoint_uses_real_records_only(client: TestClient, world: dict, store: FakeDataStore) -> None:
    store.records["r1"] = record("r1", edited=True, edits=1)
    store.records["syn"] = record("syn", source="synthetic", ai=False)
    body = client.get("/admin/ai-quality", headers=world["demo"]).json()
    assert body["recordsConsidered"] == 1 and body["correctionRate"] == 1.0


# --- overview ---


def test_overview_counts_and_synthetic_toggle(
    client: TestClient, world: dict, store: FakeDataStore, clock: FixedClock
) -> None:
    ensure_synthetic_households(store, clock)
    with_syn = client.get("/admin/overview?range=7d", headers=world["demo"]).json()
    assert with_syn["pickupsUpcoming"]["requested"] == 2 and with_syn["pickupsToday"]["requested"] == 0
    assert with_syn["pickupsInRange"]["requested"] == 0  # both are scheduled for tomorrow
    assert with_syn["syntheticHouseholds"] == 50 and with_syn["activeHouseholds"] == 50
    assert with_syn["bagsProcessed"] == 100
    assert with_syn["collectors"] == 2
    assert sum(with_syn["categories"].values()) == with_syn["totalQuantity"] > 0
    assert {z["zone"] for z in with_syn["zones"]} >= {"colombo-05", "nugegoda"}
    client.app.state.admin_cache.clear()
    without = client.get("/admin/overview?range=7d&synthetic=exclude", headers=world["demo"]).json()
    assert without["activeHouseholds"] == 0 and without["totalQuantity"] == 0
    assert client.get("/admin/overview?range=1y", headers=world["demo"]).status_code == 422


def test_admin_reads_are_cached_and_writes_clear_cache(
    client: TestClient, world: dict, store: FakeDataStore
) -> None:
    first = client.get("/admin/overview", headers=world["demo"]).json()
    store.pickups.clear()
    assert client.get("/admin/overview", headers=world["demo"]).json()["pickupsUpcoming"] == first["pickupsUpcoming"]
    client.app.state.admin_cache.clear()
    assert client.get("/admin/overview", headers=world["demo"]).json()["pickupsUpcoming"]["requested"] == 0


def test_ttl_cache_expires() -> None:
    now = [0.0]
    cache = TTLCache(ttl_s=60, clock=lambda: now[0])
    calls = []
    cache.get_or_set(("k",), lambda: calls.append(1) or 1)
    cache.get_or_set(("k",), lambda: calls.append(1) or 1)
    now[0] = 61
    cache.get_or_set(("k",), lambda: calls.append(1) or 1)
    assert len(calls) == 2


# --- people ---


def test_real_admin_creates_staff_with_zones(client: TestClient, world: dict, identity: FakeIdentity,
                                             users: FakeUserStore) -> None:
    body = {"email": "Nimal@Example.com", "name": "Nimal", "role": "collector", "zones": ["colombo-05"]}
    created = client.post("/admin/staff", json=body, headers=world["real"]).json()
    assert created["setupLink"].startswith("https://")
    uid = created["uid"]
    assert identity.claims[uid] == {"role": "collector"}
    assert users.docs[uid].zones == ["colombo-05"] and users.docs[uid].email == "nimal@example.com"
    again = client.post("/admin/staff", json=body | {"email": "nimal@example.com"}, headers=world["real"])
    assert again.status_code == 409
    bad = client.post("/admin/staff", json=body | {"email": "x@example.com", "zones": []}, headers=world["real"])
    assert bad.status_code == 422
    zones = client.patch(f"/admin/users/{uid}/zones", json={"zones": ["nugegoda"]}, headers=world["real"])
    assert zones.json()["zones"] == ["nugegoda"]


def test_users_by_role(client: TestClient, world: dict) -> None:
    collectors = client.get("/admin/users?role=collector", headers=world["demo"]).json()
    assert {u["uid"] for u in collectors} == {"col-1", "synthetic-collector-b"}
    assert any(u["isSynthetic"] for u in collectors)


def test_demo_admin_sees_real_emails_masked(client: TestClient, world: dict, users: FakeUserStore) -> None:
    users.upsert("res-1", "Nimal", "nimal@example.com", Role.RESIDENT)
    demo = {u["uid"]: u for u in client.get("/admin/users", headers=world["demo"]).json()}
    real = {u["uid"]: u for u in client.get("/admin/users", headers=world["real"]).json()}
    assert demo["res-1"]["email"] == "n•••@example.com"
    assert real["res-1"]["email"] == "nimal@example.com"


# --- partners + demo keys ---


def test_partner_engagement_and_key_management(client: TestClient, world: dict, store: FakeDataStore,
                                                clock: FixedClock) -> None:
    upsert_partner(store, clock, "greencart-lk", rotate_key=False)
    for _ in range(4):
        store.count_swap_event("greencart-lk", "2026-03-10", "GC-001", "impressions")
    store.count_swap_event("greencart-lk", "2026-03-10", "GC-001", "clicks")
    rows = {p["id"]: p for p in client.get("/admin/partners", headers=world["demo"]).json()}
    gc = rows["greencart-lk"]
    assert (gc["impressions"], gc["clicks"], gc["ctr"], gc["catalogSize"]) == (4, 1, 0.25, 20)
    assert gc["topProducts"][0]["sku"] == "GC-001" and gc["isDemo"] is True
    # Real admin: create a partner -> key shown once, only the hash stored.
    created = client.post("/admin/partners", json={"name": "Lanka Refill Co"}, headers=world["real"]).json()
    assert created["partner"]["id"] == "lanka-refill-co" and created["apiKey"].startswith("etp.lanka-refill-co.")
    assert created["apiKey"] not in str(store.partners["lanka-refill-co"])
    rotated = client.post("/admin/partners/lanka-refill-co/rotate-key", headers=world["real"]).json()
    assert rotated["apiKey"] != created["apiKey"]
    demo_rotate = client.post("/admin/partners/greencart-lk/rotate-key", headers=world["real"])
    assert demo_rotate.status_code == 409 and demo_rotate.json()["detail"] == "demo_partner_key_managed_by_seed"
    assert client.post("/admin/partners", json={"name": "Lanka Refill Co"}, headers=world["real"]).status_code == 409


def test_demo_key_only_for_demo_partners(client: TestClient, world: dict) -> None:
    ok = client.get("/admin/partners/greencart-lk/demo-key", headers=world["demo"]).json()
    assert ok["apiKey"].startswith("etp.greencart-lk.")
    assert client.get("/admin/partners/lanka-refill-co/demo-key", headers=world["demo"]).status_code == 404


def test_secret_reader_refuses_non_demo_secrets_before_calling_secret_manager() -> None:
    reader = SecretManagerDemoKeyReader.__new__(SecretManagerDemoKeyReader)  # no client: must not be needed
    with pytest.raises(Exception) as err:
        reader.read("some-real-partner")
    assert getattr(err.value, "detail", "") == "not_a_demo_partner"


def test_stats_carry_zone_and_synthetic_flag(store: FakeDataStore, clock: FixedClock) -> None:
    ensure_synthetic_households(store, clock)
    stats = store.stats["synthetic-hh-31"]
    assert stats.isSynthetic is True and stats.zone == "nugegoda"
    assert stats.realOnly["bags"] == 0  # synthetic records don't count as real


def test_role_enum_includes_admin() -> None:
    assert Role.ADMIN.value == "admin" and BagStatus.PROCESSED.value == "processed"
