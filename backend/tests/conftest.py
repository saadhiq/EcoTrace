import pytest
from fastapi.testclient import TestClient

from app.auth import get_identity, get_user_store
from app.deps import get_clock, get_store
from app.main import create_app
from app.routes.operator import get_classifier, get_photo_store
from tests.fakes import (
    FakeClassifier,
    FakeDataStore,
    FakeIdentity,
    FakePhotoStore,
    FakeUserStore,
    FixedClock,
)


@pytest.fixture
def identity() -> FakeIdentity:
    return FakeIdentity()


@pytest.fixture
def users() -> FakeUserStore:
    return FakeUserStore()


@pytest.fixture
def store() -> FakeDataStore:
    return FakeDataStore()


@pytest.fixture
def clock() -> FixedClock:
    return FixedClock()


@pytest.fixture
def classifier() -> FakeClassifier:
    return FakeClassifier()


@pytest.fixture
def photo_store() -> FakePhotoStore:
    return FakePhotoStore()


@pytest.fixture
def client(
    monkeypatch: pytest.MonkeyPatch,
    identity: FakeIdentity,
    users: FakeUserStore,
    store: FakeDataStore,
    clock: FixedClock,
    classifier: FakeClassifier,
    photo_store: FakePhotoStore,
) -> TestClient:
    monkeypatch.setenv("ALLOWED_ORIGINS", "http://localhost:3000")
    monkeypatch.setenv("DEMO_RATE_LIMIT_PER_MIN", "3")
    monkeypatch.setenv("ANALYZE_RATE_LIMIT_PER_MIN", "5")
    app = create_app()
    app.dependency_overrides[get_identity] = lambda: identity
    app.dependency_overrides[get_user_store] = lambda: users
    app.dependency_overrides[get_store] = lambda: store
    app.dependency_overrides[get_clock] = lambda: clock
    app.dependency_overrides[get_classifier] = lambda: classifier
    app.dependency_overrides[get_photo_store] = lambda: photo_store
    return TestClient(app)
