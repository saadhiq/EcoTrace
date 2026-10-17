"""Stats on confirm, tips caching/fallback, consent history, pickup details, demo history."""

from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.ai.gemini import AiError
from app.ai.tips import STATIC_TIPS, parse_tips
from app.demo_history import DEMO_HISTORY_IDS, ensure_demo_resident_history
from app.insights import compute_stats, rebuild
from tests.fakes import FakeClassifier, FakeDataStore, FakeIdentity, FakeTipGenerator, FakeUserStore, FixedClock
from tests.test_operator import ai_items, analyze, confirm, warehouse  # noqa: F401 - fixture


def tips(client: TestClient, w: dict, lang: str = "en"):  # noqa: ANN201
    return client.post(f"/residents/me/tips?lang={lang}", headers=w["home"]["headers"])


def process_bag(client: TestClient, w: dict, classifier: FakeClassifier, code: str, quality: str = "mixed",
                hazards: list[str] | None = None) -> dict[str, Any]:
    analyze(client, w, code)
    response = confirm(client, w, code, ai_items(classifier), quality, hazards)
    assert response.status_code == 200, response.text
    return response.json()


# --- stats + ledger updated in the confirm batch ---


def test_confirm_updates_stats_and_ledger_in_same_batch(
    client: TestClient, warehouse: dict, store: FakeDataStore, classifier: FakeClassifier  # noqa: F811
) -> None:
    code = warehouse["codes"][0]
    analyze(client, warehouse, code)
    commits_before = store.commits
    confirm(client, warehouse, code, ai_items(classifier), "good")
    assert store.commits == commits_before + 1  # one atomic batch
    stats = store.stats["res-1"]
    assert stats.bagsProcessed == 1
    assert stats.categories["plastic"].quantity == 4 and stats.categories["metal"].quantity == 2
    assert stats.segregation["good"] == 1
    assert stats.ecoScore is not None and stats.points == 15
    assert set(store.ledger["res-1"]) == {f"{code}-bag_processed", f"{code}-good_segregation"}
    assert store.records[code].pickupDate == "2026-03-11"


def test_stats_accumulate_and_match_full_rebuild(
    client: TestClient, warehouse: dict, store: FakeDataStore, classifier: FakeClassifier, clock: FixedClock  # noqa: F811
) -> None:
    first, second = warehouse["codes"]
    process_bag(client, warehouse, classifier, first, "good", ["battery"])
    process_bag(client, warehouse, classifier, second, "poor")
    stats = store.stats["res-1"]
    assert stats.bagsProcessed == 2 and stats.pickupsProcessed == 1
    assert stats.points == (10 + 5 + 5) + 10
    rebuilt, ledger = rebuild(store, clock.now(), "res-1")
    assert rebuilt.statsHash == stats.statsHash
    assert sum(e.points for e in ledger) == stats.points == sum(e.points for e in store.ledger["res-1"].values())


# --- tips ---


def test_new_household_gets_static_starter_tips_without_gemini(
    client: TestClient, identity: FakeIdentity, tip_generator: FakeTipGenerator
) -> None:
    from tests.helpers import onboard

    home = onboard(client, identity, "res-new")
    response = client.post("/residents/me/tips?lang=si", headers=home["headers"])
    assert response.status_code == 200
    body = response.json()
    assert body["source"] == "starter"
    assert [t["title"] for t in body["tips"]] == [t.title for t in STATIC_TIPS["si"]]
    assert tip_generator.calls == []


def test_tips_are_generated_then_cached_until_stats_change(
    client: TestClient, warehouse: dict, classifier: FakeClassifier, tip_generator: FakeTipGenerator  # noqa: F811
) -> None:
    first, second = warehouse["codes"]
    process_bag(client, warehouse, classifier, first)
    one = tips(client, warehouse).json()
    assert one["source"] == "gemini" and one["model"] == "fake-gemini" and one["latencyMs"] == 321
    assert len(one["tips"]) == 3
    two = tips(client, warehouse).json()
    assert two["source"] == "cache" and two["tips"] == one["tips"]
    assert len(tip_generator.calls) == 1  # no Gemini call while stats are unchanged
    # Payload sent to Gemini is aggregated only.
    payload, lang = tip_generator.calls[0]
    assert lang == "en" and "quantityByCategory" in payload and "ECO-" not in str(payload)
    process_bag(client, warehouse, classifier, second)  # stats change
    assert tips(client, warehouse).json()["source"] == "gemini"
    assert len(tip_generator.calls) == 2


def test_tips_are_cached_per_language(
    client: TestClient, warehouse: dict, classifier: FakeClassifier, tip_generator: FakeTipGenerator  # noqa: F811
) -> None:
    process_bag(client, warehouse, classifier, warehouse["codes"][0])
    for lang in ["en", "si", "ta", "si", "ta", "en"]:
        assert tips(client, warehouse, lang).json()["lang"] == lang
    assert [lang for _, lang in tip_generator.calls] == ["en", "si", "ta"]


def test_tips_fall_back_to_static_when_gemini_fails_and_are_not_cached(
    client: TestClient, warehouse: dict, store: FakeDataStore, classifier: FakeClassifier,  # noqa: F811
    tip_generator: FakeTipGenerator,
) -> None:
    process_bag(client, warehouse, classifier, warehouse["codes"][0])
    tip_generator.error = AiError("unavailable", "timeout")
    body = tips(client, warehouse, "ta").json()
    assert body["source"] == "fallback"
    assert [t["title"] for t in body["tips"]] == [t.title for t in STATIC_TIPS["ta"]]
    assert ("res-1", "ta") not in store.tips
    tip_generator.error = None
    assert tips(client, warehouse, "ta").json()["source"] == "gemini"  # retried next time


def test_tips_fallback_prefers_stale_personal_tips(
    client: TestClient, warehouse: dict, classifier: FakeClassifier, tip_generator: FakeTipGenerator  # noqa: F811
) -> None:
    first, second = warehouse["codes"]
    process_bag(client, warehouse, classifier, first)
    personal = tips(client, warehouse).json()["tips"]
    process_bag(client, warehouse, classifier, second)
    tip_generator.error = AiError("invalid_output", "garbage")
    body = tips(client, warehouse).json()
    assert body["source"] == "fallback" and body["tips"] == personal


def test_tips_validation(client: TestClient, warehouse: dict) -> None:  # noqa: F811
    assert tips(client, warehouse, "fr").status_code == 422
    assert client.post("/residents/me/tips", headers=warehouse["op"]).status_code == 403


def test_parse_tips_is_defensive() -> None:
    parsed = parse_tips({"tips": [{"title": "A", "body": "B", "category": "weird"}, {"title": ""}, "x",
                                  {"title": "C", "body": "D", "category": "glass"},
                                  {"title": "E", "body": "F", "category": "metal"},
                                  {"title": "G", "body": "H", "category": "metal"}]})
    assert [t.category for t in parsed] == ["other", "glass", "metal"]
    with pytest.raises(AiError):
        parse_tips({"tips": []})


# --- pickup details ---


def test_pickup_details_show_final_items_without_photos_or_ai(
    client: TestClient, warehouse: dict, classifier: FakeClassifier  # noqa: F811
) -> None:
    first, second = warehouse["codes"]
    process_bag(client, warehouse, classifier, first, "good", ["battery"])
    response = client.get(f"/residents/me/pickups/{warehouse['pid']}/details", headers=warehouse["home"]["headers"])
    assert response.status_code == 200
    body = response.json()
    assert [b["code"] for b in body["bags"]] == [first, second]
    done, waiting = body["bags"]
    assert done["status"] == "processed" and done["segregationQuality"] == "good"
    assert done["hazardFlags"] == ["battery"] and len(done["items"]) == 3
    assert waiting["status"] == "at_warehouse" and waiting["items"] == []
    text = response.text
    assert "photoPaths" not in text and "aiResult" not in text and "confidence" not in text and "gs://" not in text


def test_pickup_details_are_owner_only(client: TestClient, warehouse: dict, identity: FakeIdentity) -> None:  # noqa: F811
    from tests.helpers import onboard

    other = onboard(client, identity, "res-2")
    url = f"/residents/me/pickups/{warehouse['pid']}/details"
    assert client.get(url, headers=other["headers"]).status_code == 404
    assert client.get(url, headers=warehouse["col"]).status_code == 403


# --- consent ---


def test_consent_is_off_by_default_and_changes_are_logged(
    client: TestClient, warehouse: dict, store: FakeDataStore, clock: FixedClock  # noqa: F811
) -> None:
    headers = warehouse["home"]["headers"]
    view = client.get("/households/me/consent", headers=headers).json()
    assert view["dataSharing"] is False and view["history"] == [] and view["textVersion"] == "v1"

    on = client.put("/households/me/consent", json={"dataSharing": True}, headers=headers).json()
    assert on["dataSharing"] is True and len(on["history"]) == 1
    assert on["history"][0]["value"] is True and on["history"][0]["by"] == "res-1"

    again = client.put("/households/me/consent", json={"dataSharing": True}, headers=headers).json()
    assert len(again["history"]) == 1  # unchanged -> not logged

    clock.advance(minutes=5)
    off = client.put("/households/me/consent", json={"dataSharing": False}, headers=headers).json()
    assert [e["value"] for e in off["history"]] == [False, True]  # newest first
    assert store.households["res-1"].consent.dataSharing is False


def test_patch_household_consent_is_also_logged(client: TestClient, warehouse: dict, store: FakeDataStore) -> None:  # noqa: F811
    headers = warehouse["home"]["headers"]
    client.patch("/households/me", json={"dataSharing": True, "phone": "+94 77 999 9999"}, headers=headers)
    assert [e.value for e in store.consent["res-1"]] == [True]
    client.patch("/households/me", json={"phone": "+94 77 888 8888"}, headers=headers)
    assert len(store.consent["res-1"]) == 1


def test_consent_requires_resident(client: TestClient, warehouse: dict) -> None:  # noqa: F811
    assert client.put("/households/me/consent", json={"dataSharing": True}, headers=warehouse["op"]).status_code == 403
    assert client.put("/households/me/consent", json={"dataSharing": "yes please"},
                      headers=warehouse["home"]["headers"]).status_code == 422


# --- demo history ---


def test_demo_history_is_synthetic_idempotent_and_rich() -> None:
    store, clock = FakeDataStore(), FixedClock()
    assert ensure_demo_resident_history(store, clock) == len(DEMO_HISTORY_IDS) == 8
    assert ensure_demo_resident_history(store, clock) == 0
    history = [store.pickups[pid] for pid in DEMO_HISTORY_IDS]
    assert all(p.isSynthetic and p.status == "processed" for p in history)
    assert [e.status for e in history[0].statusHistory] == [
        "requested", "assigned", "collected", "delivered", "processed"
    ]
    assert history[0].date < history[-1].date <= "2026-03-10"
    records = [r for r in store.records.values() if r.householdId == "demo-resident"]
    assert len(records) == 9 and all(r.isSynthetic and r.source == "synthetic" and r.aiResult is None for r in records)
    assert any(i.brand == "Elephant House" for r in records for i in r.finalItems)
    stats = store.stats["demo-resident"]
    assert stats.pickupsProcessed == 8 and stats.ecoScore == 74 and stats.points == 120
    assert stats == compute_stats(records, clock.now()).model_copy(update={"lastUpdated": stats.lastUpdated})


def test_demo_resident_login_seeds_history(client: TestClient, store: FakeDataStore, users: FakeUserStore) -> None:
    assert client.post("/auth/demo/resident").status_code == 200
    assert store.stats["demo-resident"].pickupsProcessed == 8
