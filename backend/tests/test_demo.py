from fastapi.testclient import TestClient

from app.demo import DEMO_ACCOUNTS, ensure_demo_user
from app.models import Role
from app.ratelimit import RateLimiter
from tests.fakes import FakeIdentity, FakeUserStore


def test_demo_creates_user_and_returns_custom_token(
    client: TestClient, identity: FakeIdentity, users: FakeUserStore
) -> None:
    response = client.post("/auth/demo/collector")
    assert response.status_code == 200
    assert response.json() == {"token": "custom-token-for-demo-collector", "role": "collector"}
    assert identity.claims["demo-collector"] == {"role": "collector"}
    assert users.docs["demo-collector"].role == Role.COLLECTOR
    assert users.docs["demo-collector"].email == "demo-collector@ecotrace.app"


def test_demo_recreates_deleted_user(
    client: TestClient, identity: FakeIdentity, users: FakeUserStore
) -> None:
    client.post("/auth/demo/operator")
    del identity.users["demo-operator"]
    del identity.claims["demo-operator"]
    del users.docs["demo-operator"]

    response = client.post("/auth/demo/operator")
    assert response.status_code == 200
    assert "demo-operator" in identity.users
    assert identity.claims["demo-operator"] == {"role": "operator"}
    assert users.docs["demo-operator"].role == Role.OPERATOR


def test_demo_resets_tampered_claim_and_doc(
    client: TestClient, identity: FakeIdentity, users: FakeUserStore
) -> None:
    client.post("/auth/demo/resident")
    identity.claims["demo-resident"] = {"role": "admin", "extra": True}
    users.upsert("demo-resident", "Hacked", None, Role.ADMIN)
    identity.users["demo-resident"].disabled = True

    response = client.post("/auth/demo/resident")
    assert response.status_code == 200
    assert identity.claims["demo-resident"] == {"role": "resident"}
    assert users.docs["demo-resident"].role == Role.RESIDENT
    assert users.docs["demo-resident"].name == "Demo Resident"
    assert identity.users["demo-resident"].disabled is False


def test_demo_invalid_role_is_400(client: TestClient, identity: FakeIdentity) -> None:
    response = client.post("/auth/demo/superuser")
    assert response.status_code == 400
    assert response.json()["detail"] == "invalid_role"
    assert identity.users == {}


def test_demo_is_rate_limited_per_ip(client: TestClient) -> None:
    # conftest sets DEMO_RATE_LIMIT_PER_MIN=3
    headers = {"X-Forwarded-For": "203.0.113.7"}
    statuses = [client.post("/auth/demo/admin", headers=headers).status_code for _ in range(4)]
    assert statuses == [200, 200, 200, 429]
    # A different client IP is unaffected.
    other = client.post("/auth/demo/admin", headers={"X-Forwarded-For": "198.51.100.1"})
    assert other.status_code == 200


def test_rate_limit_ignores_spoofed_leading_forwarded_entries(client: TestClient) -> None:
    for i in range(3):
        headers = {"X-Forwarded-For": f"10.0.0.{i}, 203.0.113.9"}
        assert client.post("/auth/demo/admin", headers=headers).status_code == 200
    headers = {"X-Forwarded-For": "10.0.0.99, 203.0.113.9"}
    assert client.post("/auth/demo/admin", headers=headers).status_code == 429


def test_rate_limiter_window_expires() -> None:
    now = [0.0]
    limiter = RateLimiter(limit=1, window_seconds=60, clock=lambda: now[0])
    assert limiter.allow("ip") is True
    assert limiter.allow("ip") is False
    now[0] = 60.0
    assert limiter.allow("ip") is True


def test_ensure_demo_user_handles_taken_email() -> None:
    identity, users = FakeIdentity(), FakeUserStore()
    identity.taken_emails.add(DEMO_ACCOUNTS[Role.ADMIN].email)
    uid = ensure_demo_user(identity, users, Role.ADMIN)
    assert uid == "demo-admin"
    assert users.docs[uid].email is None
    assert identity.claims[uid] == {"role": "admin"}
