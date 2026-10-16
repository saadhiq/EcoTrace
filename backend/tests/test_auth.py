from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from app.auth import get_identity, require_role
from app.models import CurrentUser, Role
from tests.fakes import FakeIdentity, FakeUserStore


def bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


# --- token verification ---


def test_me_without_token_is_401(client: TestClient) -> None:
    response = client.get("/me")
    assert response.status_code == 401
    assert response.json()["detail"] == "missing_token"


def test_me_with_invalid_token_is_401(client: TestClient) -> None:
    response = client.get("/me", headers=bearer("forged"))
    assert response.status_code == 401
    assert response.json()["detail"] == "invalid_token"


def test_me_with_non_bearer_scheme_is_401(client: TestClient, identity: FakeIdentity) -> None:
    identity.issue("t1", "u1", role="resident")
    response = client.get("/me", headers={"Authorization": "Basic t1"})
    assert response.status_code == 401


def test_me_unregistered_is_403(client: TestClient, identity: FakeIdentity) -> None:
    identity.issue("t1", "u1", email="a@example.com")
    response = client.get("/me", headers=bearer("t1"))
    assert response.status_code == 403
    assert response.json()["detail"] == "not_registered"


def test_me_returns_profile_with_role_from_claim(
    client: TestClient, identity: FakeIdentity, users: FakeUserStore
) -> None:
    users.upsert("u1", "Asha", "a@example.com", Role.RESIDENT)
    identity.issue("t1", "u1", email="a@example.com", role="collector")
    response = client.get("/me", headers=bearer("t1"))
    assert response.status_code == 200
    body = response.json()
    assert body["name"] == "Asha"
    # The claim is the source of truth, even if the mirror is stale.
    assert body["role"] == "collector"


# --- require_role ---


def _role_app(identity: FakeIdentity) -> TestClient:
    app = FastAPI()

    @app.get("/admin-only")
    def admin_only(user: CurrentUser = Depends(require_role(Role.ADMIN))) -> dict[str, str]:
        return {"uid": user.uid}

    @app.get("/staff")
    def staff(
        user: CurrentUser = Depends(require_role(Role.COLLECTOR, Role.OPERATOR)),
    ) -> dict[str, str]:
        return {"uid": user.uid}

    app.dependency_overrides[get_identity] = lambda: identity
    return TestClient(app)


def test_require_role_allows_matching_role(identity: FakeIdentity) -> None:
    identity.issue("admin", "a1", role="admin")
    assert _role_app(identity).get("/admin-only", headers=bearer("admin")).status_code == 200


def test_require_role_rejects_other_role(identity: FakeIdentity) -> None:
    identity.issue("res", "r1", role="resident")
    response = _role_app(identity).get("/admin-only", headers=bearer("res"))
    assert response.status_code == 403
    assert response.json()["detail"] == "forbidden"


def test_require_role_accepts_any_listed_role(identity: FakeIdentity) -> None:
    identity.issue("op", "o1", role="operator")
    assert _role_app(identity).get("/staff", headers=bearer("op")).status_code == 200


def test_require_role_rejects_unknown_role_claim(identity: FakeIdentity) -> None:
    identity.issue("weird", "w1", role="superuser")
    response = _role_app(identity).get("/admin-only", headers=bearer("weird"))
    assert response.status_code == 403
    assert response.json()["detail"] == "not_registered"


# --- /auth/register ---


def test_register_creates_resident(
    client: TestClient, identity: FakeIdentity, users: FakeUserStore
) -> None:
    identity.add_user("u1", email="a@example.com")
    identity.issue("t1", "u1", email="a@example.com")
    response = client.post("/auth/register", json={"name": "Asha"}, headers=bearer("t1"))
    assert response.status_code == 200
    assert response.json()["refreshToken"] is True
    assert identity.claims["u1"] == {"role": "resident"}
    assert users.docs["u1"].name == "Asha"
    assert users.docs["u1"].role == Role.RESIDENT


def test_register_twice_is_noop(
    client: TestClient, identity: FakeIdentity, users: FakeUserStore
) -> None:
    identity.add_user("u1", email="a@example.com")
    identity.issue("t1", "u1", email="a@example.com")
    client.post("/auth/register", json={"name": "Asha"}, headers=bearer("t1"))
    created = users.docs["u1"].createdAt
    response = client.post("/auth/register", json={"name": "Other"}, headers=bearer("t1"))
    assert response.status_code == 200
    assert users.docs["u1"].name == "Asha"
    assert users.docs["u1"].createdAt == created


def test_register_never_downgrades_staff_even_with_stale_token(
    client: TestClient, identity: FakeIdentity
) -> None:
    identity.add_user("c1", role=Role.COLLECTOR, email="c@example.com")
    identity.issue("stale", "c1", email="c@example.com")  # token minted before the claim
    response = client.post("/auth/register", headers=bearer("stale"))
    assert response.status_code == 200
    assert response.json()["profile"]["role"] == "collector"
    assert response.json()["refreshToken"] is True
    assert identity.claims["c1"] == {"role": "collector"}


def test_register_requires_token(client: TestClient) -> None:
    assert client.post("/auth/register").status_code == 401
