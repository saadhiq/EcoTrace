"""One-off pre-judging cleanup of DEMO data (demo resident only). Dry run by default; --apply writes.

- Marks every non-synthetic wasteRecord isTest=true (all were produced by development/testing runs);
  insights and the AI-quality panel ignore them.
- Re-dates processed demo pickups that were collected early against a future date to the day they
  were actually collected (pickup, routes mirror and records' pickupDate).
- Deletes abandoned demo pickups (stale requested, cancelled, delivered-but-never-processed) with their
  routes mirror, their bags still attached to them, and leftover draft analyses.

Afterwards run scripts/backfill_stats.py.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from app.clock import SystemClock, local_today  # noqa: E402
from app.firebase import firestore_client  # noqa: E402

DEMO_HOUSEHOLD = "demo-resident"


def colombo_day(ts) -> str:  # noqa: ANN001
    from datetime import timedelta

    return (ts + timedelta(hours=5, minutes=30)).date().isoformat()


def main(apply: bool) -> None:
    db = firestore_client()
    today = local_today(SystemClock()).isoformat()
    batch = db.batch()
    ops = 0

    def note(msg: str) -> None:
        print(("APPLY " if apply else "DRY   ") + msg)

    # 1. Development/test records.
    for snap in db.collection("wasteRecords").stream():
        d = snap.to_dict()
        if d.get("isSynthetic") or d.get("source") == "synthetic":
            continue
        if d.get("status") == "draft":
            note(f"delete draft record {snap.id} (pickup {d.get('pickupId')})")
            batch.delete(snap.reference)
        elif not d.get("isTest"):
            note(f"mark isTest record {snap.id} ({d.get('source')})")
            batch.update(snap.reference, {"isTest": True})
        ops += 1

    # 2/3. Demo pickups.
    for snap in db.collection("pickups").where("householdId", "==", DEMO_HOUSEHOLD).stream():
        p = snap.to_dict()
        if p.get("isSynthetic"):
            continue
        status, day = p["status"], p["date"]
        history = {e["status"]: e["at"] for e in p.get("statusHistory", [])}
        if status == "processed" and day > today:
            new_day = colombo_day(history["collected"])
            note(f"re-date processed pickup {snap.id}: {day} -> {new_day}")
            batch.update(snap.reference, {"date": new_day})
            route = db.collection("routes").document(snap.id)
            if route.get().exists:
                batch.update(route, {"date": new_day})
            for code in p.get("bagCodes", []):
                rec = db.collection("wasteRecords").document(code)
                if rec.get().exists:
                    batch.update(rec, {"pickupDate": new_day})
            ops += 1
        elif status == "cancelled" or (status == "requested" and day < today) or (status == "delivered" and day > today):
            note(f"delete abandoned pickup {snap.id} ({status}, {day})")
            batch.delete(snap.reference)
            batch.delete(db.collection("routes").document(snap.id))
            for code in p.get("bagCodes", []):
                bag = db.collection("bags").document(code).get()
                if bag.exists and bag.to_dict().get("pickupId") == snap.id:
                    note(f"  delete its bag {code} ({bag.to_dict().get('status')})")
                    batch.delete(bag.reference)
            ops += 1
    print(f"{ops} change(s)")
    if apply:
        batch.commit()
        print("committed")


if __name__ == "__main__":
    main("--apply" in sys.argv)
