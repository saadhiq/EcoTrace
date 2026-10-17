"""Synthetic history for the demo resident: ~2 months of processed pickups.

Gives the insights dashboard (score, breakdown, trend, points) realistic data.
Every pickup, bag and waste record is marked isSynthetic=True so analytics and
the AI benchmark can exclude them. Idempotent: fixed pickup ids, skipped when
they already exist.
"""

from datetime import UTC, datetime, time, timedelta

from app import services
from app.bagcodes import generate_code
from app.clock import COLOMBO, Clock, local_today
from app.demo import DEMO_ACCOUNTS, SEED, ensure_demo_resident_data
from app.insights import rebuild
from app.models import (
    Bag,
    BagStatus,
    Pickup,
    PickupStatus,
    Role,
    StatusEvent,
    TimeSlot,
    WasteItem,
    WasteRecord,
    WasteRecordStatus,
)
from app.store import DataStore
from app.transitions import advance_bag, advance_pickup

Item = tuple[str, str, str, str, str | None, int, bool]  # name, category, material, type, brand, qty, recyclable
BagSpec = tuple[str, list[str], list[Item]]  # segregation, hazard flags, items

DEMO_HISTORY: list[tuple[int, str, list[BagSpec]]] = [  # (days ago, slot, bags)
    (56, "morning", [("mixed", [], [
        ("Cream soda bottle", "plastic", "PET", "soft drink bottle", "Elephant House", 3, True),
        ("Milk powder pouch", "plastic", "laminate", "food pouch", "Anchor", 1, False),
        ("Newspaper", "paper_cardboard", "paper", "newspaper", "Lankadeepa", 6, True),
        ("Vegetable peels", "organic", "food", "kitchen scraps", None, 1, False),
    ])]),
    (49, "afternoon", [("good", [], [
        ("Coconut shells", "organic", "coconut husk", "kitchen waste", None, 4, False),
        ("Kitchen scraps", "organic", "food", "kitchen scraps", None, 1, False),
    ])]),
    (42, "morning", [
        ("good", [], [
            ("Jam jar", "glass", "glass", "food jar", "Kist", 2, True),
            ("Soft drink can", "metal", "aluminium", "drink can", "Coca-Cola", 4, True),
        ]),
        ("poor", ["battery"], [
            ("Used AA batteries", "hazardous", "alkaline", "battery", "Eveready", 4, False),
            ("Biscuit wrappers", "plastic", "film", "wrapper", "Munchee", 3, False),
            ("Rice leftovers", "organic", "food", "food waste", None, 1, False),
        ]),
    ]),
    (35, "afternoon", [("mixed", [], [
        ("Yoghurt cups", "plastic", "PP", "yoghurt cup", "Highland", 6, True),
        ("Biscuit box", "paper_cardboard", "cardboard", "food box", "Maliban", 2, True),
        ("Used tea leaves", "organic", "food", "kitchen scraps", None, 1, False),
    ])]),
    (28, "morning", [("good", [], [
        ("Cardboard boxes", "paper_cardboard", "cardboard", "shipping box", None, 3, True),
        ("Newspaper", "paper_cardboard", "paper", "newspaper", "Daily Mirror", 8, True),
    ])]),
    (21, "afternoon", [("good", ["battery"], [
        ("Old mobile phone", "e_waste", "mixed", "mobile phone", "Nokia", 1, True),
        ("Phone charger", "e_waste", "plastic/copper", "charger", None, 1, True),
    ])]),
    (14, "morning", [("mixed", [], [
        ("Soap wrapper", "paper_cardboard", "paper", "wrapper", "Sunlight", 3, True),
        ("Plastic shopping bags", "plastic", "LDPE film", "carrier bag", None, 5, False),
        ("Torn T-shirt", "textile", "cotton", "clothing", None, 1, False),
        ("Rice and curry leftovers", "organic", "food", "food waste", None, 1, False),
    ])]),
    (7, "afternoon", [("good", [], [
        ("Ginger beer bottle", "glass", "glass", "soft drink bottle", "Elephant House", 4, True),
        ("Beer can", "metal", "aluminium", "drink can", "Lion", 3, True),
    ])]),
]
DEMO_HISTORY_IDS = [f"demo-hist-{i:02d}" for i in range(1, len(DEMO_HISTORY) + 1)]


class _BackdatedClock:
    """Clock pinned to a past moment, advanced step by step while seeding."""

    def __init__(self, start: datetime) -> None:
        self.current = start

    def now(self) -> datetime:
        return self.current

    def step(self, **delta: float) -> "_BackdatedClock":
        self.current += timedelta(**delta)
        return self


def _new_codes(store: DataStore, count: int) -> list[str]:
    codes: set[str] = set()
    while len(codes) < count:
        code = generate_code()
        if not store.get_bags([code]):
            codes.add(code)
    return sorted(codes)


def _local(day, hour: int, minute: int = 0) -> datetime:  # noqa: ANN001
    return datetime.combine(day, time(hour, minute), tzinfo=COLOMBO).astimezone(UTC)


def ensure_demo_resident_history(store: DataStore, clock: Clock) -> int:
    """Create any missing synthetic history pickups; returns how many were created."""
    uid = DEMO_ACCOUNTS[Role.RESIDENT].uid
    existing = store.get_pickups(DEMO_HISTORY_IDS)
    if len(existing) == len(DEMO_HISTORY_IDS):
        return 0
    household = store.get_household(uid)
    if household is None:
        ensure_demo_resident_data(store, clock)
        household = store.get_household(uid)
    assert household is not None
    collector = DEMO_ACCOUNTS[Role.COLLECTOR].uid
    operator = DEMO_ACCOUNTS[Role.OPERATOR].uid
    today = local_today(clock)
    created = 0

    for pickup_id, (days_ago, slot, bag_specs) in zip(DEMO_HISTORY_IDS, DEMO_HISTORY, strict=True):
        if pickup_id in existing:
            continue
        day = today - timedelta(days=days_ago)
        bc = _BackdatedClock(_local(day - timedelta(days=2), 19))
        codes = _new_codes(store, len(bag_specs))
        issued = [
            Bag(code=code, householdId=uid, ownerUid=uid, status=BagStatus.ISSUED, issuedAt=bc.now(),
                statusHistory=[StatusEvent(status=BagStatus.ISSUED, at=bc.now(), by=SEED)], isSynthetic=True)
            for code in codes
        ]
        store.create_bags(issued)
        bc.step(hours=1)
        pickup = Pickup(
            id=pickup_id, householdId=uid, residentUid=uid, zone=household.zone, date=day.isoformat(),
            timeSlot=TimeSlot(slot), bagCodes=codes, status=PickupStatus.REQUESTED,
            statusHistory=[StatusEvent(status=PickupStatus.REQUESTED, at=bc.now(), by=uid)],
            createdAt=bc.now(), isSynthetic=True,
        )
        bags = [advance_bag(b, BagStatus.SCHEDULED, by=uid, clock=bc, pickupId=pickup_id) for b in issued]
        bc.step(hours=14)
        pickup = advance_pickup(pickup, PickupStatus.ASSIGNED, by=collector, clock=bc,
                                collectorUid=collector, assignedAt=bc.now())
        bc.current = _local(day, 9 if slot == "morning" else 14, 20)
        bags = [advance_bag(b, BagStatus.COLLECTED, by=collector, clock=bc, collectorUid=collector) for b in bags]
        pickup = advance_pickup(pickup, PickupStatus.COLLECTED, by=collector, clock=bc, collectedAt=bc.now())
        bc.step(hours=3)
        bags = [advance_bag(b, BagStatus.AT_WAREHOUSE, by=collector, clock=bc) for b in bags]
        pickup = advance_pickup(pickup, PickupStatus.DELIVERED, by=collector, clock=bc, deliveredAt=bc.now())
        bc.step(hours=18)
        records = []
        for bag, (quality, hazards, items) in zip(bags, bag_specs, strict=True):
            bc.step(minutes=5)
            records.append(WasteRecord(
                bagCode=bag.code, householdId=uid, pickupId=pickup_id, status=WasteRecordStatus.CONFIRMED,
                finalItems=[
                    WasteItem(name=n, category=c, material=m, productType=t, brand=b, quantity=q, recyclable=r)
                    for n, c, m, t, b, q, r in items
                ],
                segregationQuality=quality, hazardFlags=hazards, edited=False, editCount=0,
                source="synthetic", operatorUid=operator, processedAt=bc.now(),
                pickupDate=day.isoformat(), isSynthetic=True,
            ))
        bags = [advance_bag(b, BagStatus.PROCESSED, by=operator, clock=bc) for b in bags]
        pickup = advance_pickup(pickup, PickupStatus.PROCESSED, by=operator, clock=bc)
        store.commit([pickup], bags, [services.route_stop(pickup, household, bags, bc)], records)
        created += 1

    if created:
        stats, ledger = rebuild(store, clock.now(), uid)
        store.commit([], [], stats=[(uid, stats)], ledger=[(uid, entry) for entry in ledger])
    return created
