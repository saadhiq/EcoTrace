"""Rebuild households/{id}/stats/summary and pointsLedger from confirmed wasteRecords.

Safe to run any time (stats are a pure function of the records; ledger ids are
deterministic). Usage (repo root, backend venv, your ADC):
    backend/.venv/Scripts/python scripts/backfill_stats.py
"""

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))
os.environ.setdefault("GOOGLE_CLOUD_PROJECT", "ecotrace-9e406")

from google.cloud.firestore import FieldFilter  # noqa: E402

from app.clock import SystemClock  # noqa: E402
from app.firebase import firestore_client  # noqa: E402
from app.insights import rebuild  # noqa: E402
from app.store import FirestoreDataStore  # noqa: E402


def main() -> None:
    store = FirestoreDataStore()
    db = firestore_client()
    confirmed = db.collection("wasteRecords").where(filter=FieldFilter("status", "==", "confirmed")).stream()
    households = sorted({snap.get("householdId") for snap in confirmed})
    now = SystemClock().now()
    for household_id in households:
        stats, ledger = rebuild(store, now, household_id)
        store.commit([], [], stats=[(household_id, stats)], ledger=[(household_id, e) for e in ledger])
        print(f"{household_id}: {stats.bagsProcessed} bags, score {stats.ecoScore}, {stats.points} points, "
              f"{len(ledger)} ledger entries")
    print(f"rebuilt {len(households)} household(s)")


if __name__ == "__main__":
    main()
