"""Swaps (consent, candidate validation, fallback, cache) and the partner API (auth, K, limits)."""

from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient

from app.ai.gemini import AiError
from app.demo_partners import ensure_synthetic_households, upsert_partner
from app.insights import compute_stats
from app.models import WasteItem, WasteRecord
from app.partner_api import K_MIN, segments, verify_key, zone_insights
from app.recommendations import find_candidates, phrase_matches, validate_picks
from app.segments import assign_segment
from tests.fakes import FakeDataStore, FakeRanker, FixedClock
from tests.helpers import auth, onboard

NOW = datetime(2026, 3, 10, tzinfo=UTC)


@pytest.fixture
def partners(store: FakeDataStore, clock: FixedClock) -> dict[str, str]:
    return {pid: upsert_partner(store, clock, pid, rotate_key=False) for pid in ["greencart-lk", "ecohome-store"]}


def give_stats(store: FakeDataStore, clock: FixedClock, uid: str, items: list[tuple[str, str, int]]) -> None:
    """Confirmed record + stats for `uid` (items: productType, category, qty)."""
    record = WasteRecord(
        bagCode=f"B-{uid}", householdId=uid, pickupId=f"p-{uid}", status="confirmed", segregationQuality="mixed",
        finalItems=[WasteItem(name=t, category=c, productType=t, quantity=q, recyclable=True) for t, c, q in items],
        processedAt=NOW, pickupDate="2026-03-01",
    )
    store.records[record.bagCode] = record
    store.stats[uid] = compute_stats([record], clock.now())


@pytest.fixture
def resident(client: TestClient, identity, store: FakeDataStore, clock: FixedClock, partners) -> dict:  # noqa: ANN001
    home = onboard(client, identity, "res-1")
    give_stats(store, clock, "res-1", [("soft drink bottle", "plastic", 14), ("carrier bag", "plastic", 5),
                                       ("kitchen scraps", "organic", 3)])
    return home


def consent(client: TestClient, home: dict, value: bool) -> None:
    assert client.put("/households/me/consent", json={"dataSharing": value}, headers=home["headers"]).status_code == 200


# --- stage 1: candidates ---


def test_phrase_matching_is_word_subset_with_plurals() -> None:
    assert phrase_matches("drink bottle", "soft drink bottles")
    assert phrase_matches("carrier bag", "Carrier_Bags")
    assert not phrase_matches("plastic bottle", "soft drink bottle")


def test_candidates_prefer_direct_matches(store: FakeDataStore, partners) -> None:  # noqa: ANN001
    catalogs = [(p, store.list_catalog(p.id)) for p in store.list_partners()]
    cands = find_candidates({"soft drink bottle": 14, "carrier bag": 5}, {"plastic": 19}, catalogs)
    direct = [c.item.sku for c in cands if c.matched]
    assert direct[:3] == ["GC-001", "GC-003", "GC-004"]
    assert all(c.matched for c in cands[: len(direct)])  # category-only matches come after


# --- stage 2: Gemini ranking validated against candidates ---


def test_hallucinated_and_duplicate_skus_are_dropped(store: FakeDataStore, partners) -> None:  # noqa: ANN001
    catalogs = [(p, store.list_catalog(p.id)) for p in store.list_partners()]
    cands = find_candidates({"soft drink bottle": 14}, {}, catalogs)
    raw = {"picks": [
        {"sku": "GC-001", "reason": "You disposed of 14 drink bottles."},
        {"sku": "FAKE-999", "reason": "Invented product"},
        {"sku": "GC-001", "reason": "duplicate"},
        {"sku": "GC-003", "reason": ""},  # no reason -> dropped
        "garbage",
    ]}
    assert [(c.item.sku, r) for c, r in validate_picks(raw, cands)] == [("GC-001", "You disposed of 14 drink bottles.")]
    assert validate_picks({"picks": [{"sku": f"X{i}", "reason": "r"} for i in range(9)]}, cands) == []
    assert validate_picks("not json", cands) == []


# --- resident swaps endpoint ---


def test_swaps_require_consent(client: TestClient, resident: dict) -> None:
    response = client.get("/residents/me/swaps", headers=resident["headers"])
    assert response.status_code == 403
    assert response.json()["detail"] == "consent_required"


def test_swaps_use_gemini_picks_and_log_impressions(
    client: TestClient, resident: dict, store: FakeDataStore, ranker: FakeRanker
) -> None:
    consent(client, resident, True)
    ranker.response = {"picks": [{"sku": "GC-004", "reason": "You threw away 5 carrier bags."},
                                 {"sku": "NOPE-1", "reason": "hallucinated"}]}
    body = client.get("/residents/me/swaps", headers=resident["headers"]).json()
    assert body["source"] == "gemini" and body["model"] == "fake-gemini"
    assert [(p["sku"], p["partnerName"], p["reason"]) for p in body["picks"]] == [
        ("GC-004", "GreenCart LK", "You threw away 5 carrier bags.")]
    payload = ranker.calls[0]
    assert "res-1" not in str(payload) and "candidates" in payload  # aggregates + candidates only
    assert store.events[("greencart-lk", "2026-03-10", "impressions", "GC-004")] == 1
    assert not any("res-1" in str(k) for k in store.events)


def test_swaps_fallback_ranking_when_gemini_fails(client: TestClient, resident: dict, ranker: FakeRanker) -> None:
    consent(client, resident, True)
    ranker.error = AiError("unavailable", "5xx")
    body = client.get("/residents/me/swaps", headers=resident["headers"]).json()
    assert body["source"] == "fallback"
    assert [p["sku"] for p in body["picks"]][:3] == ["GC-001", "GC-003", "GC-004"]
    assert body["picks"][0]["reason"].startswith("You disposed of 14 soft drink bottles")
    assert len(body["picks"]) == 4


def test_swaps_fallback_when_all_picks_invalid(client: TestClient, resident: dict, ranker: FakeRanker) -> None:
    consent(client, resident, True)
    ranker.response = {"picks": [{"sku": "FAKE", "reason": "x"}]}
    assert client.get("/residents/me/swaps", headers=resident["headers"]).json()["source"] == "fallback"


def test_swaps_cached_until_stats_change_and_deleted_on_withdrawal(
    client: TestClient, resident: dict, store: FakeDataStore, clock: FixedClock, ranker: FakeRanker
) -> None:
    consent(client, resident, True)
    client.get("/residents/me/swaps", headers=resident["headers"])
    assert client.get("/residents/me/swaps", headers=resident["headers"]).json()["source"] == "cache"
    assert len(ranker.calls) == 1
    give_stats(store, clock, "res-1", [("carrier bag", "plastic", 9)])
    assert client.get("/residents/me/swaps", headers=resident["headers"]).json()["source"] == "gemini"
    consent(client, resident, False)
    assert "res-1" not in store.swaps
    assert client.get("/residents/me/swaps", headers=resident["headers"]).status_code == 403


def test_swap_click_is_counted_anonymously(client: TestClient, resident: dict, store: FakeDataStore) -> None:
    consent(client, resident, True)
    sku = client.get("/residents/me/swaps", headers=resident["headers"]).json()["picks"][0]["sku"]
    response = client.post(f"/residents/me/swaps/{sku}/click", headers=resident["headers"])
    assert response.json()["url"].startswith("/demo-store/?partner=")
    assert store.events[("greencart-lk", "2026-03-10", "clicks", sku)] == 1
    assert client.post("/residents/me/swaps/NOPE/click", headers=resident["headers"]).status_code == 404


# --- segments ---


@pytest.mark.parametrize("cats,types,hazard_bags,good,bags,expected", [
    ({"hazardous": 2, "plastic": 8}, {}, 0, 0, 1, "e-waste-disposer"),
    ({"plastic": 10}, {}, 2, 0, 2, "e-waste-disposer"),
    ({"plastic": 6, "metal": 4}, {"drink bottle": 3}, 0, 0, 1, "beverage-plastic-heavy"),
    ({"plastic": 6, "metal": 4}, {"wrapper": 10}, 0, 0, 1, "mixed-household"),
    ({"organic": 4, "glass": 6}, {}, 0, 0, 1, "organic-heavy-family"),
    ({"paper_cardboard": 3, "glass": 7}, {}, 0, 0, 1, "paper-and-packaging"),
    ({"glass": 10}, {}, 0, 7, 10, "well-segregated"),
    ({"glass": 10}, {}, 0, 6, 10, "mixed-household"),
    ({}, {}, 0, 0, 0, None),
])
def test_segment_rules(cats: dict, types: dict, hazard_bags: int, good: int, bags: int, expected: str | None) -> None:
    assert assign_segment(cats, types, hazard_bags, good, bags) == expected


# --- partner API ---


@pytest.fixture
def synthetic(store: FakeDataStore, clock: FixedClock, partners) -> dict[str, str]:  # noqa: ANN001
    ensure_synthetic_households(store, clock)
    return partners


def key_headers(key: str) -> dict[str, str]:
    return {"X-API-Key": key}


def test_partner_auth(client: TestClient, synthetic: dict, store: FakeDataStore) -> None:
    assert client.get("/partner/v1/segments").status_code == 401
    assert client.get("/partner/v1/segments", headers=key_headers("nope")).status_code == 401
    forged = synthetic["greencart-lk"][:-4] + "AAAA"
    assert client.get("/partner/v1/segments", headers=key_headers(forged)).status_code == 401
    store.partners["ecohome-store"] = store.partners["ecohome-store"].model_copy(update={"active": False})
    assert client.get("/partner/v1/segments", headers=key_headers(synthetic["ecohome-store"])).status_code == 401
    assert client.get("/partner/v1/segments", headers=key_headers(synthetic["greencart-lk"])).status_code == 200
    # Only the hash is stored.
    assert synthetic["greencart-lk"] not in str(store.partners["greencart-lk"])


def test_partner_rate_limit(client: TestClient, synthetic: dict) -> None:
    statuses = [client.get("/partner/v1/segments", headers=key_headers(synthetic["greencart-lk"])).status_code
                for _ in range(5)]
    assert statuses == [200] * 4 + [429]  # conftest: 4/min
    # Separate budget per key.
    assert client.get("/partner/v1/segments", headers=key_headers(synthetic["ecohome-store"])).status_code == 200


def withdraw(store: FakeDataStore, hid: str) -> None:
    h = store.households[hid]
    store.households[hid] = h.model_copy(update={"consent": h.consent.model_copy(update={"dataSharing": False})})


def test_segments_k_threshold_and_consent(store: FakeDataStore, synthetic: dict) -> None:
    result = segments(store)
    assert result.consentingHouseholds == 43  # 50 synthetic, 7 without consent
    visible = {s.name: s.households for s in result.segments}
    assert visible["mixed-household"] == K_MIN and visible["beverage-plastic-heavy"] == 9
    assert all(n >= K_MIN for n in visible.values()) and result.suppressedSegments == 0
    # Withdraw consent for one mixed household -> 4 left -> suppressed, never shown with < K.
    hid = next(h for h, s in store.stats.items() if s.segment == "mixed-household" and store.households[h].consent.dataSharing)
    withdraw(store, hid)
    after = segments(store)
    assert "mixed-household" not in {s.name for s in after.segments}
    assert after.suppressedSegments == 1 and after.consentingHouseholds == 42


def test_segments_response_has_no_household_data(client: TestClient, synthetic: dict) -> None:
    text = client.get("/partner/v1/segments", headers=key_headers(synthetic["greencart-lk"])).text
    assert "synthetic-hh" not in text and "household " not in text.lower().replace("households", "")


def test_segment_recommendations_only_own_catalog(client: TestClient, synthetic: dict) -> None:
    url = "/partner/v1/segments/beverage-plastic-heavy/recommendations"
    gc = client.get(url, headers=key_headers(synthetic["greencart-lk"])).json()
    assert gc["households"] == 9 and gc["recommendations"]
    assert all(r["sku"].startswith("GC-") for r in gc["recommendations"])
    assert "each on average" in gc["recommendations"][0]["reason"]
    eh = client.get(url, headers=key_headers(synthetic["ecohome-store"])).json()
    assert all(r["sku"].startswith("EH-") for r in eh["recommendations"])
    assert client.get("/partner/v1/segments/e-waste-disposer/recommendations",
                      headers=key_headers(synthetic["ecohome-store"])).status_code == 200
    assert client.get("/partner/v1/segments/nope/recommendations", headers=key_headers(synthetic["greencart-lk"])).status_code == 404


def test_suppressed_segment_recommendations_404(client: TestClient, synthetic: dict, store: FakeDataStore) -> None:
    hid = next(h for h, s in store.stats.items() if s.segment == "mixed-household" and store.households[h].consent.dataSharing)
    withdraw(store, hid)
    url = "/partner/v1/segments/mixed-household/recommendations"
    assert client.get(url, headers=key_headers(synthetic["greencart-lk"])).status_code == 404


def test_zone_insights_k_threshold(client: TestClient, synthetic: dict, store: FakeDataStore) -> None:
    hid = next(h for h, hh in store.households.items() if hh.zone == "rajagiriya" and hh.consent.dataSharing)
    withdraw(store, hid)  # rajagiriya: 5 -> 4 consenting -> suppressed
    body = client.get("/partner/v1/insights", headers=key_headers(synthetic["greencart-lk"])).json()
    zones = {z["zone"]: z for z in body["zones"]}
    assert zones["colombo-05"]["suppressed"] is False and zones["colombo-05"]["households"] >= K_MIN
    assert zones["rajagiriya"]["suppressed"] is True and zones["rajagiriya"]["months"] == []
    assert zones["rajagiriya"]["households"] is None
    for z in body["zones"]:
        assert all(m["households"] >= K_MIN for m in z["months"])
    one = client.get("/partner/v1/insights?zone=colombo-07", headers=key_headers(synthetic["greencart-lk"])).json()
    assert [z["zone"] for z in one["zones"]] == ["colombo-07"]
    assert client.get("/partner/v1/insights?zone=mars", headers=key_headers(synthetic["greencart-lk"])).status_code == 422
    # A month with < K contributors is hidden even in a visible zone.
    result = zone_insights(store, "colombo-07")
    assert all(m.households >= K_MIN for m in result.zones[0].months)


def test_verify_key_rejects_malformed(store: FakeDataStore, synthetic: dict) -> None:
    for bad in [None, "", "etp", "etp.greencart-lk", "x.greencart-lk.abc", "etp.unknown.abc"]:
        with pytest.raises(Exception):  # noqa: B017
            verify_key(store, bad)


def test_openapi_documents_partner_api(client: TestClient) -> None:
    spec = client.get("/openapi.json").json()
    assert spec["tags"][0]["name"] == "Partner API v1"
    assert "APIKeyHeader" in spec["components"]["securitySchemes"]
    assert "/partner/v1/segments" in spec["paths"]


def test_stats_trend_uses_processed_date(clock: FixedClock) -> None:
    record = WasteRecord(bagCode="B1", householdId="h", pickupId="p1", status="confirmed", segregationQuality="good",
                         finalItems=[WasteItem(name="x", category="glass", quantity=1)],
                         processedAt=datetime(2026, 2, 3, 20, 0, tzinfo=UTC), pickupDate="2026-03-20")
    stats = compute_stats([record], clock.now())
    assert stats.byPickup[0].date == "2026-02-04"  # Colombo date of processedAt, not the pickup date
    assert stats.monthly == {"2026-02": {"glass": 1}}


def test_auth_header_name_is_x_api_key(client: TestClient, synthetic: dict) -> None:
    response = client.get("/partner/v1/segments", headers=auth(synthetic["greencart-lk"]))  # Bearer is not accepted
    assert response.status_code == 401
