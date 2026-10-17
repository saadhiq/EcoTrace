"""Create or repair the four passwordless demo accounts, the demo resident's
household data, the demo collector's zones + a pickup for today, and a bag
in the warehouse queue for the demo operator
(idempotent and bounded, never deletes anything).

Uses the same logic as POST /auth/demo/{role}. Runs with your Application
Default Credentials (`gcloud auth application-default login`).

Usage (from repo root, using the backend venv):
    backend/.venv/Scripts/python scripts/seed_demo_users.py      # Windows
    backend/.venv/bin/python scripts/seed_demo_users.py          # macOS/Linux
"""

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))
os.environ.setdefault("GOOGLE_CLOUD_PROJECT", "ecotrace-9e406")

from app.clock import SystemClock  # noqa: E402
from app.demo import (  # noqa: E402
    DEMO_ACCOUNTS,
    ensure_demo_collector_data,
    ensure_demo_operator_data,
    ensure_demo_resident_data,
    ensure_demo_user,
)
from app.demo_history import ensure_demo_resident_history  # noqa: E402
from app.identity import FirebaseIdentityAdmin  # noqa: E402
from app.models import Role  # noqa: E402
from app.store import FirestoreDataStore  # noqa: E402
from app.users import FirestoreUserStore  # noqa: E402


def main() -> None:
    identity = FirebaseIdentityAdmin()
    users = FirestoreUserStore()
    store = FirestoreDataStore()
    print(f"Project: {os.environ['GOOGLE_CLOUD_PROJECT']}")
    for role, account in DEMO_ACCOUNTS.items():
        existed = identity.get_user(account.uid) is not None
        ensure_demo_user(identity, users, role)
        print(f"  {'repaired' if existed else 'created '} {account.uid:<15} role={role.value}")

    resident = DEMO_ACCOUNTS[Role.RESIDENT].uid
    clock = SystemClock()
    ensure_demo_resident_data(store, clock)
    history = ensure_demo_resident_history(store, clock)
    print(f"  demo resident history: {history} synthetic pickups created")
    created = ensure_demo_collector_data(store, users, clock)
    print(f"  demo collector: {'new pickup ' + created if created else 'already has a pickup today'}")
    queued = ensure_demo_operator_data(store, clock)
    print(f"  demo operator: {'queued pickup ' + queued if queued else 'queue already has bags'}")
    bags = store.list_bags(resident)
    pickups = store.list_pickups(resident)
    print(f"  demo household: {len(bags)} bags, pickups: "
          + ", ".join(f"{p.date} {p.status.value}" for p in pickups))


if __name__ == "__main__":
    main()
