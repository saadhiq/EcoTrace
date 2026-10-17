"""Household segments: deterministic, documented rules over aggregated stats.

Rules (not ML) because the data is tiny (tens of households): clusters would be
unstable, partners need segment names that mean the same thing every week, and
every assignment can be explained and checked by hand. Future work: BigQuery ML
k-means once there are thousands of households. Rules are evaluated in order;
the first match wins. Shares are by item quantity.
"""

from dataclasses import dataclass

SEGMENT_VERSION = "v1"
DRINK_WORDS = ("bottle", "can", "cup", "carton")


@dataclass(frozen=True)
class Segment:
    name: str
    title: str
    description: str


SEGMENTS: list[Segment] = [
    Segment("e-waste-disposer", "E-waste disposer",
            "E-waste + hazardous items are at least 15% of their waste, or 2+ bags carried hazard flags."),
    Segment("beverage-plastic-heavy", "Beverage-plastic heavy",
            "Plastic + metal are at least 45% of their waste and drink containers (bottles, cans, cups, cartons) "
            "at least 25%."),
    Segment("organic-heavy-family", "Organic-heavy family", "Organic (food) waste is at least 35% of their waste."),
    Segment("paper-and-packaging", "Paper & packaging", "Paper and cardboard are at least 30% of their waste."),
    Segment("well-segregated", "Well-segregated", "At least 70% of their bags were rated well sorted."),
    Segment("mixed-household", "Mixed household", "No single pattern dominates."),
]
SEGMENTS_BY_NAME = {s.name: s for s in SEGMENTS}


def assign_segment(
    category_qty: dict[str, int],
    product_types: dict[str, int],
    hazard_bags: int,
    good_bags: int,
    bags: int,
) -> str | None:
    """The household's segment, or None before its first processed bag."""
    total = sum(category_qty.values())
    if bags == 0 or total == 0:
        return None

    def share(*cats: str) -> float:
        return sum(category_qty.get(c, 0) for c in cats) / total

    drinks = sum(q for name, q in product_types.items() if any(w in name.split() for w in DRINK_WORDS))
    if share("e_waste", "hazardous") >= 0.15 or hazard_bags >= 2:
        return "e-waste-disposer"
    if share("plastic", "metal") >= 0.45 and drinks / total >= 0.25:
        return "beverage-plastic-heavy"
    if share("organic") >= 0.35:
        return "organic-heavy-family"
    if share("paper_cardboard") >= 0.30:
        return "paper-and-packaging"
    if good_bags / bags >= 0.70:
        return "well-segregated"
    return "mixed-household"
