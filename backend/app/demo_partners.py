"""Demo partners (fictional) and synthetic households for swaps + the partner API.

Everything here is clearly fictional and marked isSynthetic=True. Idempotent.
"""

from datetime import timedelta

from app.clock import Clock, local_today
from app.demo import DEMO_ACCOUNTS
from app.insights import rebuild
from app.models import (
    CatalogItem,
    Consent,
    Household,
    Partner,
    Role,
    UserProfile,
    WasteItem,
    WasteRecord,
    WasteRecordStatus,
)
from app.partner_api import generate_key
from app.residents import set_consent
from app.store import DataStore
from app.users import UserStore
from app.zones import ZONE_IDS

# (sku, name, category, replaces, ecoBenefit, price LKR)
_P = tuple[str, str, str, list[str], str, float]
GREENCART: list[_P] = [
    ("GC-001", "Stainless steel water bottle (750 ml)", "plastic", ["drink bottle", "water bottle", "plastic bottle", "beverage bottle"], "Replaces ~150 single-use bottles a year", 2450),
    ("GC-002", "Insulated coffee tumbler", "paper_cardboard", ["coffee cup", "paper cup", "disposable cup"], "Avoids ~200 disposable cups a year", 2900),
    ("GC-003", "Glass drink bottle with silicone sleeve", "plastic", ["drink bottle", "soft drink bottle"], "Reusable for years; fully recyclable glass", 1850),
    ("GC-004", "Reusable cloth shopping bag", "plastic", ["carrier bag", "shopping bag", "plastic bag"], "Replaces ~300 plastic carrier bags", 650),
    ("GC-005", "Mesh produce bags (set of 5)", "plastic", ["produce bag", "plastic bag"], "No more thin plastic bags for vegetables", 950),
    ("GC-006", "Beeswax food wraps (set of 3)", "plastic", ["food wrapper", "wrapper", "cling film"], "Replaces cling film and food wrappers", 1500),
    ("GC-007", "Silicone food storage bags (set of 4)", "plastic", ["food pouch", "zip bag"], "Reusable 1,000+ times", 2200),
    ("GC-008", "Bamboo cutlery travel set", "plastic", ["plastic cutlery", "disposable cutlery"], "Skip single-use cutlery with takeaways", 1200),
    ("GC-009", "Stainless steel lunch box", "plastic", ["takeaway box", "food container", "lunch packet"], "Replaces takeaway boxes and lunch sheets", 3100),
    ("GC-010", "Dish-soap concentrate refill", "plastic", ["soap bottle", "detergent bottle"], "One refill pouch replaces 4 bottles", 890),
    ("GC-011", "Solid shampoo bar", "plastic", ["shampoo bottle"], "Plastic-free; lasts like 2-3 bottles", 1100),
    ("GC-012", "Bamboo toothbrush (pack of 4)", "plastic", ["toothbrush"], "Compostable handle", 780),
    ("GC-013", "Bulk laundry liquid refill (5 L)", "plastic", ["detergent bottle", "detergent pouch"], "Refill at home; fewer bottles", 3400),
    ("GC-014", "Stainless steel straws (set of 4)", "plastic", ["straw"], "Replaces hundreds of plastic straws", 600),
    ("GC-015", "Glass yoghurt jars (set of 6)", "plastic", ["yoghurt cup"], "Make or buy yoghurt in returnable jars", 1650),
    ("GC-016", "Returnable milk can (dairy refill scheme)", "plastic", ["milk packet", "milk carton"], "Refill fresh milk without packaging", 2000),
    ("GC-017", "Cotton table napkins (set of 6)", "paper_cardboard", ["paper napkin", "tissue"], "Washable alternative to paper napkins", 1400),
    ("GC-018", "Reusable cloth coffee filter", "organic", ["coffee filter", "tea bag"], "Replaces paper filters and tea bags", 700),
    ("GC-019", "Water filter jug", "plastic", ["water bottle"], "Filtered tap water instead of bottled water", 5200),
    ("GC-020", "Collapsible silicone cup", "paper_cardboard", ["paper cup", "disposable cup"], "Pocket-sized reusable cup", 1300),
]
ECOHOME: list[_P] = [
    ("EH-001", "Kitchen compost bin (10 L)", "organic", ["kitchen scraps", "food waste", "vegetable peel"], "Turns food scraps into compost", 2800),
    ("EH-002", "Home compost tumbler", "organic", ["kitchen waste", "food waste", "coconut shell"], "Faster compost for bigger households", 14500),
    ("EH-003", "Bokashi starter kit", "organic", ["food waste", "rice leftovers", "kitchen scraps"], "Ferments cooked food waste too", 4200),
    ("EH-004", "Rechargeable AA batteries (4) + charger", "hazardous", ["battery", "aa battery"], "One set replaces ~500 disposable batteries", 4900),
    ("EH-005", "Battery collection box", "hazardous", ["battery"], "Keep used batteries out of the bin", 450),
    ("EH-006", "E-waste take-back envelope", "e_waste", ["mobile phone", "charger", "cable"], "Prepaid return for small electronics", 300),
    ("EH-007", "Solar phone charger", "e_waste", ["charger"], "Fewer chargers and power banks", 6500),
    ("EH-008", "Long-life LED bulb (pack of 3)", "e_waste", ["light bulb", "bulb"], "Lasts 15x longer than old bulbs", 1800),
    ("EH-009", "Recycled-paper notebook set", "paper_cardboard", ["newspaper", "paper"], "Made from post-consumer paper", 950),
    ("EH-010", "Digital newspaper subscription voucher", "paper_cardboard", ["newspaper"], "News without the daily paper pile", 1500),
    ("EH-011", "Reusable delivery crate", "paper_cardboard", ["shipping box", "cardboard box"], "Replaces cardboard boxes for deliveries", 2600),
    ("EH-012", "Glass storage jars (set of 4)", "glass", ["food jar", "jar"], "Reuse instead of buying jarred food", 2100),
    ("EH-013", "Cloth diaper starter kit", "other", ["diaper"], "Reusable for years", 9800),
    ("EH-014", "Menstrual cup", "other", ["sanitary pad"], "Replaces ~2,000 pads", 2500),
    ("EH-015", "Washable cleaning cloths (set of 5)", "textile", ["wet wipe", "paper towel"], "Replaces disposable wipes", 900),
    ("EH-016", "Clothes repair kit", "textile", ["clothing", "t shirt"], "Mend instead of throwing away", 1250),
    ("EH-017", "Textile recycling bag", "textile", ["clothing", "fabric"], "Send old clothes to textile recycling", 200),
    ("EH-018", "Refillable spray bottle + cleaner concentrate", "plastic", ["spray bottle", "cleaner bottle"], "One bottle, many refills", 1600),
    ("EH-019", "Coconut-coir scrubbers (pack of 3)", "plastic", ["sponge", "scrubber"], "Compostable kitchen scrubbers", 550),
    ("EH-020", "Planter made from recycled plastic", "plastic", [], "Gives plastic waste a second life", 1900),
]
DEMO_PARTNERS = {"greencart-lk": ("GreenCart LK", GREENCART), "ecohome-store": ("EcoHome Store", ECOHOME)}


def catalog_items(partner_id: str, rows: list[_P]) -> list[CatalogItem]:
    # Fictional partners: products open EcoTrace's own demo store page (relative URL).
    return [
        CatalogItem(sku=sku, name=name, category=cat, tags=[cat], replaces=rep, ecoBenefit=benefit, price=price,
                    url=f"/demo-store/?partner={partner_id}&sku={sku}")
        for sku, name, cat, rep, benefit, price in rows
    ]


def upsert_partner(store: DataStore, clock: Clock, partner_id: str, rotate_key: bool) -> str | None:
    """Create/refresh a demo partner + catalog. Returns a NEW API key if one was generated."""
    name, rows = DEMO_PARTNERS[partner_id]
    existing = store.get_partner(partner_id)
    key = None
    if existing is None or rotate_key:
        key, key_hash, prefix = generate_key(partner_id)
        partner = Partner(id=partner_id, name=name, apiKeyHash=key_hash, keyPrefix=prefix, active=True,
                          createdAt=existing.createdAt if existing else clock.now(), isSynthetic=True)
    else:
        partner = existing
    store.save_partner(partner, catalog_items(partner_id, rows))
    return key


# --- synthetic households ---

_I = tuple[str, str, str, str, int, bool]  # name, category, material, productType, qty, recyclable
PROFILES: dict[str, tuple[str, list[_I]]] = {
    "beverage": ("mixed", [("PET drink bottle", "plastic", "PET", "drink bottle", 9, True),
                           ("Drink can", "metal", "aluminium", "drink can", 5, True),
                           ("Plastic carrier bag", "plastic", "LDPE", "carrier bag", 3, False),
                           ("Snack wrapper", "plastic", "film", "wrapper", 2, False)]),
    "organic": ("good", [("Kitchen scraps", "organic", "food", "kitchen scraps", 6, False),
                         ("Coconut shells", "organic", "coconut husk", "coconut shell", 4, False),
                         ("Vegetable peels", "organic", "food", "vegetable peel", 3, False),
                         ("Milk powder pouch", "plastic", "laminate", "food pouch", 2, False)]),
    "paper": ("good", [("Newspaper", "paper_cardboard", "paper", "newspaper", 10, True),
                       ("Shipping box", "paper_cardboard", "cardboard", "shipping box", 4, True),
                       ("Food jar", "glass", "glass", "food jar", 2, True)]),
    "ewaste": ("mixed", [("Used batteries", "hazardous", "alkaline", "battery", 4, False),
                         ("Old charger", "e_waste", "mixed", "charger", 1, True),
                         ("Old mobile phone", "e_waste", "mixed", "mobile phone", 1, True),
                         ("Newspaper", "paper_cardboard", "paper", "newspaper", 3, True)]),
    "sorted": ("good", [("Food jar", "glass", "glass", "food jar", 3, True),
                        ("Yoghurt cup", "plastic", "PP", "yoghurt cup", 3, True),
                        ("Newspaper", "paper_cardboard", "paper", "newspaper", 2, True),
                        ("Kitchen scraps", "organic", "food", "kitchen scraps", 2, False)]),
    "mixed": ("poor", [("Old clothing", "textile", "cotton", "clothing", 2, False),
                       ("Carrier bag", "plastic", "LDPE", "carrier bag", 3, False),
                       ("Kitchen scraps", "organic", "food", "kitchen scraps", 3, False),
                       ("Food jar", "glass", "glass", "food jar", 2, True)]),
}
# 30 households: (profile, consenting?) - ~77% consent; mix chosen so some segments clear K=5 and some don't.
PLAN: list[tuple[str, bool]] = (
    [("beverage", True)] * 6 + [("beverage", False)]
    + [("organic", True)] * 5 + [("organic", False)]
    + [("paper", True)] * 3 + [("paper", False)] * 2
    + [("ewaste", True)] * 2 + [("ewaste", False)]
    + [("sorted", True)] * 5 + [("sorted", False)]
    + [("mixed", True)] * 2 + [("mixed", False)]
    # Step 6b: 20 more, all consenting, so more segments/zones clear K=5.
    + [("paper", True)] * 3 + [("ewaste", True)] * 4 + [("mixed", True)] * 3
    + [("beverage", True)] * 3 + [("organic", True)] * 3 + [("sorted", True)] * 4
)
ZONE_PATTERN = ["colombo-07", "colombo-05", "colombo-07", "colombo-05", "nugegoda", "colombo-07",
                "colombo-05", "dehiwala", "colombo-07", "colombo-05", "nugegoda", "colombo-03"]
EXTRA_ZONES = ["nugegoda", "dehiwala", "colombo-03", "rajagiriya"]  # households 31-50
SYNTHETIC_IDS = [f"synthetic-hh-{i:02d}" for i in range(1, len(PLAN) + 1)]
SYNTHETIC_COLLECTOR = "synthetic-collector-b"


def _zone(i: int) -> str:
    return ZONE_PATTERN[i % len(ZONE_PATTERN)] if i < 30 else EXTRA_ZONES[(i - 30) % len(EXTRA_ZONES)]


def ensure_synthetic_households(store: DataStore, clock: Clock) -> int:
    """Create missing synthetic households (2 processed bags each) and their stats."""
    created = 0
    today = local_today(clock)
    for i, (hid, (profile, consenting)) in enumerate(zip(SYNTHETIC_IDS, PLAN, strict=True)):
        if store.get_household(hid) is not None:
            continue
        quality, items = PROFILES[profile]
        household = Household(
            id=hid, ownerUid=hid, name=f"Synthetic household {i + 1:02d}", phone="+94 70 000 0000",
            addressLine="(synthetic)", zone=_zone(i),
            consent=Consent(dataSharing=consenting, updatedAt=clock.now()), createdAt=clock.now(), isSynthetic=True,
        )
        records = []
        for n, days_ago in enumerate([10 + (i * 3) % 25, 40 + (i * 5) % 20]):
            day = today - timedelta(days=days_ago)
            scale = 1 + (i + n) % 2  # some variety between households
            records.append(WasteRecord(
                bagCode=f"SYN-{i + 1:02d}-{n + 1}", householdId=hid, pickupId=f"{hid}-p{n + 1}",
                status=WasteRecordStatus.CONFIRMED, source="synthetic", isSynthetic=True,
                finalItems=[WasteItem(name=nm, category=c, material=m, productType=t, quantity=q * scale, recyclable=r)
                            for nm, c, m, t, q, r in items],
                segregationQuality=quality, hazardFlags=["battery"] if profile == "ewaste" else [],
                processedAt=clock.now() - timedelta(days=days_ago), pickupDate=day.isoformat(),
            ))
        store.commit([], [], records=records, households=[household])
        stats, _ = rebuild(store, clock.now(), hid)
        store.commit([], [], stats=[(hid, stats)])
        created += 1
    return created


def ensure_synthetic_collector(users: UserStore) -> bool:
    """A users-only collector (no login account) so admins can demo reassignment."""
    if users.get(SYNTHETIC_COLLECTOR) is not None:
        return False
    users.save(UserProfile(uid=SYNTHETIC_COLLECTOR, name="Synthetic Collector B", email=None, role=Role.COLLECTOR,
                           zones=sorted(ZONE_IDS), isSynthetic=True))
    return True


def ensure_demo_resident_consent(store: DataStore, clock: Clock) -> bool:
    """Seed-time only: turn the demo resident's data sharing ON (judges can turn it off)."""
    uid = DEMO_ACCOUNTS[Role.RESIDENT].uid
    household = store.get_household(uid)
    if household is None or household.consent.dataSharing:
        return False
    set_consent(store, clock, household, True, by="seed")
    return True
