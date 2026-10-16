import pytest
from fastapi.testclient import TestClient

from app.auth import get_identity, get_user_store
from app.main import create_app
from tests.fakes import FakeIdentity, FakeUserStore


@pytest.fixture
def identity() -> FakeIdentity:
    return FakeIdentity()


@pytest.fixture
def users() -> FakeUserStore:
    return FakeUserStore()


@pytest.fixture
def client(
    monkeypatch: pytest.MonkeyPatch, identity: FakeIdentity, users: FakeUserStore
) -> TestClient:
    monkeypatch.setenv("ALLOWED_ORIGINS", "http://localhost:3000")
    monkeypatch.setenv("DEMO_RATE_LIMIT_PER_MIN", "3")
    app = create_app()
    app.dependency_overrides[get_identity] = lambda: identity
    app.dependency_overrides[get_user_store] = lambda: users
    return TestClient(app)
