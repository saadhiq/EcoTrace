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
from app.demo_partners import (  # noqa: E402
    DEMO_PARTNERS,
    ensure_demo_resident_consent,
    ensure_synthetic_households,
    upsert_partner,
)
from app.identity import FirebaseIdentityAdmin  # noqa: E402
from app.models import Role  # noqa: E402
from app.store import FirestoreDataStore  # noqa: E402
from app.users import FirestoreUserStore  # noqa: E402


def partner_secret_id(partner_id: str) -> str:
    return f"partner-api-key-{partner_id}"


def secret_has_version(client, project: str, secret_id: str) -> bool:  # noqa: ANN001
    from google.api_core.exceptions import NotFound

    try:
        client.access_secret_version(name=f"projects/{project}/secrets/{secret_id}/versions/latest")
        return True
    except NotFound:
        return False


def store_secret(client, project: str, secret_id: str, value: str) -> None:  # noqa: ANN001
    from google.api_core.exceptions import AlreadyExists

    try:
        client.create_secret(request={
            "parent": f"projects/{project}",
            "secret_id": secret_id,
            "secret": {"replication": {"user_managed": {"replicas": [{"location": "asia-south1"}]}},
                       "labels": {"app": "ecotrace", "kind": "demo-partner-key"}},
        })
    except AlreadyExists:
        pass
    client.add_secret_version(request={"parent": f"projects/{project}/secrets/{secret_id}",
                                       "payload": {"data": value.encode()}})


def seed_partners(store, clock, project: str) -> None:  # noqa: ANN001
    """Demo partners + catalogs. A key is generated only if the partner or its secret is missing;
    the plain key goes ONLY to Secret Manager (Firestore keeps the SHA-256 hash)."""
    from google.cloud import secretmanager

    client = secretmanager.SecretManagerServiceClient()
    for partner_id in DEMO_PARTNERS:
        secret_id = partner_secret_id(partner_id)
        has_secret = secret_has_version(client, project, secret_id)
        key = upsert_partner(store, clock, partner_id, rotate_key=not has_secret)
        if key:
            store_secret(client, project, secret_id, key)
            print(f"  partner {partner_id}: new API key stored in Secret Manager ({secret_id})")
        else:
            print(f"  partner {partner_id}: catalog refreshed, existing key kept")


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
    seed_partners(store, clock, os.environ["GOOGLE_CLOUD_PROJECT"])
    print(f"  synthetic households: {ensure_synthetic_households(store, clock)} created")
    if ensure_demo_resident_consent(store, clock):
        print("  demo resident: data sharing turned ON (judges can turn it off)")
    queued = ensure_demo_operator_data(store, clock)
    print(f"  demo operator: {'queued pickup ' + queued if queued else 'queue already has bags'}")
    bags = store.list_bags(resident)
    pickups = store.list_pickups(resident)
    print(f"  demo household: {len(bags)} bags, pickups: "
          + ", ".join(f"{p.date} {p.status.value}" for p in pickups))


if __name__ == "__main__":
    main()
