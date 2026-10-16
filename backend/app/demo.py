"""Public demo accounts: one per role, passwordless, signed in via custom tokens."""

from dataclasses import dataclass

from app.identity import IdentityAdmin
from app.models import Role
from app.users import UserStore


@dataclass(frozen=True)
class DemoAccount:
    uid: str
    email: str
    name: str


DEMO_ACCOUNTS: dict[Role, DemoAccount] = {
    Role.RESIDENT: DemoAccount("demo-resident", "demo-resident@ecotrace.app", "Demo Resident"),
    Role.COLLECTOR: DemoAccount("demo-collector", "demo-collector@ecotrace.app", "Demo Collector"),
    Role.OPERATOR: DemoAccount("demo-operator", "demo-operator@ecotrace.app", "Demo Operator"),
    Role.ADMIN: DemoAccount("demo-admin", "demo-admin@ecotrace.app", "Demo Admin"),
}


def ensure_demo_user(identity: IdentityAdmin, users: UserStore, role: Role) -> str:
    """Create or repair the demo user for `role`; returns its uid. Idempotent."""
    account = DEMO_ACCOUNTS[role]
    existing = identity.get_user(account.uid)
    if existing is None:
        created = identity.create_user(account.uid, account.email, account.name)
        email = created.email
    else:
        identity.reset_user(account.uid, account.name)
        email = existing.email
    identity.set_role(account.uid, role)
    users.upsert(account.uid, account.name, email, role)
    return account.uid
