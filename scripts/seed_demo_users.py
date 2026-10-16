"""Create or repair the four passwordless demo accounts (idempotent).

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

from app.demo import DEMO_ACCOUNTS, ensure_demo_user  # noqa: E402
from app.identity import FirebaseIdentityAdmin  # noqa: E402
from app.users import FirestoreUserStore  # noqa: E402


def main() -> None:
    identity = FirebaseIdentityAdmin()
    users = FirestoreUserStore()
    print(f"Project: {os.environ['GOOGLE_CLOUD_PROJECT']}")
    for role, account in DEMO_ACCOUNTS.items():
        existed = identity.get_user(account.uid) is not None
        ensure_demo_user(identity, users, role)
        print(f"  {'repaired' if existed else 'created '} {account.uid:<15} role={role.value}")


if __name__ == "__main__":
    main()
