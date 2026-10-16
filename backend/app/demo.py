"""Public demo accounts: one per role, passwordless, signed in via custom tokens."""

from dataclasses import dataclass
from datetime import timedelta

from app import services
from app.clock import Clock, local_today
from app.identity import IdentityAdmin
from app.models import CANCELLABLE_PICKUP_STATUSES, BagStatus, PickupStatus, Role, TimeSlot
from app.store import DataStore
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

DEMO_MIN_BAGS = 10
DEMO_MIN_ISSUED = 5
SEED = "seed"


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


def ensure_demo_resident_data(store: DataStore, clock: Clock) -> None:
    """Non-destructively keep the shared demo resident usable. Idempotent.

    Guarantees: a household; at least 10 bags with at least 5 unused; one
    upcoming active pickup; one cancelled pickup. Never deletes anything.
    """
    uid = DEMO_ACCOUNTS[Role.RESIDENT].uid
    household = store.get_household(uid)
    if household is None:
        household, _ = services.create_household(
            store,
            clock,
            uid,
            name="Perera Household",
            phone="+94 77 123 4567",
            address_line="12 Flower Road",
            zone="colombo-07",
        )

    bags = store.list_bags(uid)
    issued = sum(1 for bag in bags if bag.status == BagStatus.ISSUED)
    top_up = max(DEMO_MIN_BAGS - len(bags), DEMO_MIN_ISSUED - issued, 0)
    top_up = min(top_up, services.MAX_UNUSED_BAGS - issued)
    if top_up > 0:
        services.issue_bags(store, clock, household, top_up, by=SEED)

    pickups = store.list_pickups(uid)
    first, _ = services.pickup_date_window(clock)
    taken = {p.date for p in pickups if p.status != PickupStatus.CANCELLED}

    def free_date(offset: int):  # noqa: ANN202
        for days in range(offset, services.MAX_DAYS_AHEAD + 1):
            day = local_today(clock) + timedelta(days=days)
            if day.isoformat() not in taken:
                taken.add(day.isoformat())
                return day
        return None

    def issued_codes(count: int) -> list[str]:
        free = [bag.code for bag in store.list_bags(uid) if bag.status == BagStatus.ISSUED]
        return free[:count]

    has_upcoming = any(
        p.status in CANCELLABLE_PICKUP_STATUSES and p.date >= first.isoformat() for p in pickups
    )
    if not has_upcoming and (day := free_date(3)):
        services.schedule_pickup(
            store,
            clock,
            uid,
            pickup_date=day,
            time_slot=TimeSlot.MORNING,
            bag_codes=issued_codes(2),
            notes="Two bags by the front gate.",
            by=SEED,
        )

    if not any(p.status == PickupStatus.CANCELLED for p in pickups) and (day := free_date(5)):
        pickup = services.schedule_pickup(
            store,
            clock,
            uid,
            pickup_date=day,
            time_slot=TimeSlot.AFTERNOON,
            bag_codes=issued_codes(1),
            by=SEED,
        )
        services.cancel_pickup(store, clock, uid, pickup.id, by=SEED)
