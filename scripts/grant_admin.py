"""Give an EXISTING Firebase user the real admin role (custom claim + users doc).

The public demo admin is read-only for accounts/partners/keys; real admin
actions (create staff, partners, rotate keys) need a real admin account.
Usage (repo root, backend venv, your ADC):
    backend/.venv/Scripts/python scripts/grant_admin.py someone@example.com
"""

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))
os.environ.setdefault("GOOGLE_CLOUD_PROJECT", "ecotrace-9e406")

from firebase_admin import auth  # noqa: E402

from app.firebase import firebase_app  # noqa: E402
from app.identity import FirebaseIdentityAdmin  # noqa: E402
from app.models import Role  # noqa: E402
from app.users import FirestoreUserStore  # noqa: E402


def main() -> None:
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    record = auth.get_user_by_email(sys.argv[1], app=firebase_app())
    FirebaseIdentityAdmin().set_role(record.uid, Role.ADMIN)
    FirestoreUserStore().upsert(record.uid, record.display_name or record.email or "Admin", record.email, Role.ADMIN)
    print(f"{record.email} ({record.uid}) is now an admin. They must sign out and in again.")


if __name__ == "__main__":
    main()
