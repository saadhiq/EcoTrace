"""Injectable dependencies for the resident-flow routes (overridden in tests)."""

from app.clock import Clock, SystemClock
from app.store import DataStore, FirestoreDataStore


def get_store() -> DataStore:
    return FirestoreDataStore()


def get_clock() -> Clock:
    return SystemClock()
