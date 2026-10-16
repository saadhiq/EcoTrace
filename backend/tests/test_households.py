from fastapi.testclient import TestClient

from app.models import BagStatus
from tests.fakes import FakeDataStore, FakeIdentity
from tests.helpers import HOUSEHOLD, auth, onboard, resident


def test_zones_are_public(client: TestClient) -> None:
    response = client.get("/zones")
    assert response.status_code == 200
    assert len(response.json()) == 6
    assert {"id": "colombo-07", "name": "Colombo 07 – Cinnamon Gardens"} in response.json()


def test_create_household_issues_five_starter_bags(
    client: TestClient, identity: FakeIdentity, store: FakeDataStore
) -> None:
    result = onboard(client, identity)
    household = result["household"]
    assert household["id"] == "res-1"
    assert household["ownerUid"] == "res-1"
    assert household["consent"]["dataSharing"] is False
    assert household["consent"]["updatedAt"] is not None
    assert len(result["bags"]) == 5
    assert all(b["status"] == "issued" and b["ownerUid"] == "res-1" for b in result["bags"])
    assert len(store.bags) == 5


def test_only_one_household_per_resident(client: TestClient, identity: FakeIdentity) -> None:
    result = onboard(client, identity)
    again = client.post("/households", json=HOUSEHOLD, headers=result["headers"])
    assert again.status_code == 409
    assert again.json()["detail"] == "household_exists"


def test_non_residents_cannot_create_households(client: TestClient, identity: FakeIdentity) -> None:
    for role in ["collector", "operator", "admin"]:
        identity.issue(role, f"{role}-1", role=role)
        response = client.post("/households", json=HOUSEHOLD, headers=auth(role))
        assert response.status_code == 403


def test_unauthenticated_requests_are_rejected(client: TestClient) -> None:
    assert client.post("/households", json=HOUSEHOLD).status_code == 401
    assert client.get("/households/me").status_code == 401
    assert client.get("/bags/mine").status_code == 401
    assert client.get("/pickups/mine").status_code == 401


def test_invalid_zone_is_rejected(client: TestClient, identity: FakeIdentity) -> None:
    response = client.post(
        "/households", json={**HOUSEHOLD, "zone": "kandy"}, headers=resident(identity)
    )
    assert response.status_code == 422
    assert response.json()["detail"] == "invalid_zone"


def test_invalid_fields_are_rejected(client: TestClient, identity: FakeIdentity) -> None:
    headers = resident(identity)
    for bad in [{"phone": "call me"}, {"name": ""}, {"addressLine": ""}, {"lat": 120}]:
        response = client.post("/households", json={**HOUSEHOLD, **bad}, headers=headers)
        assert response.status_code == 422, bad


def test_get_household_before_onboarding_is_404(client: TestClient, identity: FakeIdentity) -> None:
    response = client.get("/households/me", headers=resident(identity))
    assert response.status_code == 404
    assert response.json()["detail"] == "no_household"


def test_patch_household_updates_fields_and_consent(
    client: TestClient, identity: FakeIdentity
) -> None:
    result = onboard(client, identity)
    before = result["household"]["consent"]["updatedAt"]
    response = client.patch(
        "/households/me",
        json={"phone": "+94 77 000 0000", "zone": "nugegoda", "dataSharing": True},
        headers=result["headers"],
    )
    assert response.status_code == 200
    body = response.json()
    assert body["phone"] == "+94 77 000 0000"
    assert body["zone"] == "nugegoda"
    assert body["name"] == HOUSEHOLD["name"]
    assert body["consent"]["dataSharing"] is True
    assert body["consent"]["updatedAt"] >= before


def test_patch_household_rejects_invalid_zone(client: TestClient, identity: FakeIdentity) -> None:
    result = onboard(client, identity)
    response = client.patch("/households/me", json={"zone": "nowhere"}, headers=result["headers"])
    assert response.status_code == 422


def test_bags_mine_lists_only_own_bags(client: TestClient, identity: FakeIdentity) -> None:
    a = onboard(client, identity, "res-a")
    onboard(client, identity, "res-b")
    bags = client.get("/bags/mine", headers=a["headers"]).json()
    assert len(bags) == 5
    assert {b["householdId"] for b in bags} == {"res-a"}


def test_request_more_issues_five(client: TestClient, identity: FakeIdentity) -> None:
    result = onboard(client, identity)
    response = client.post("/bags/request-more", headers=result["headers"])
    assert response.status_code == 201
    assert len(response.json()) == 5
    assert len(client.get("/bags/mine", headers=result["headers"]).json()) == 10


def test_request_more_caps_unused_bags_at_twenty(
    client: TestClient, identity: FakeIdentity, store: FakeDataStore
) -> None:
    result = onboard(client, identity)
    for _ in range(3):
        assert client.post("/bags/request-more", headers=result["headers"]).status_code == 201
    # 20 unused now -> refused.
    response = client.post("/bags/request-more", headers=result["headers"])
    assert response.status_code == 409
    assert response.json()["detail"] == "bag_limit_reached"

    # Use 3 bags; only 3 more may be issued (not 5).
    for bag in list(store.bags.values())[:3]:
        store.bags[bag.code] = bag.model_copy(update={"status": BagStatus.COLLECTED})
    response = client.post("/bags/request-more", headers=result["headers"])
    assert response.status_code == 201
    assert len(response.json()) == 3


def test_request_more_requires_household(client: TestClient, identity: FakeIdentity) -> None:
    assert client.post("/bags/request-more", headers=resident(identity)).status_code == 404


def test_bag_code_collisions_are_retried(
    client: TestClient, identity: FakeIdentity, store: FakeDataStore, monkeypatch
) -> None:
    import app.services as services

    first = [f"ECO-AAAA-{i}{i}" for i in "23456"]
    second = [f"ECO-BBBB-{i}{i}" for i in "23456"]
    codes = iter(first + second)
    monkeypatch.setattr(services, "generate_code", lambda: next(codes))
    store.reserved_codes.add(first[2])  # one code in the first batch is taken
    result = onboard(client, identity)
    assert {b["code"] for b in result["bags"]} == set(second)
    assert not any(code in store.bags for code in first)
