"""Eco score formula, points ledger and stats aggregation (pure functions)."""

from datetime import UTC, datetime

import pytest

from app.insights import (
    POINTS_BAG,
    awards_for,
    compute_stats,
    eco_score,
    score_parts,
    stats_hash,
    tips_payload,
)
from app.models import WasteItem, WasteRecord

NOW = datetime(2026, 3, 10, tzinfo=UTC)


def rec(
    code: str = "ECO-AAAA-AA",
    quality: str = "good",
    hazards: list[str] | None = None,
    items: list[tuple[str, int, bool]] | None = None,
    pickup: str = "p1",
    date: str = "2026-03-01",
    status: str = "confirmed",
) -> WasteRecord:
    items = items if items is not None else [("plastic", 2, True)]
    return WasteRecord(
        bagCode=code, householdId="h1", pickupId=pickup, status=status,
        finalItems=[WasteItem(name=f"{c} thing", category=c, quantity=q, recyclable=r) for c, q, r in items],
        segregationQuality=quality, hazardFlags=hazards or [], processedAt=NOW, pickupDate=date,
    )


# --- score formula ---


def test_no_bags_means_no_score() -> None:
    assert eco_score([]) is None
    assert score_parts([]) is None
    assert compute_stats([], NOW).ecoScore is None


def test_perfect_household_scores_100() -> None:
    assert eco_score([rec(quality="good", items=[("glass", 3, True)])]) == 100


def test_worst_household_scores_zero() -> None:
    r = rec(quality="poor", hazards=["battery"], items=[("organic", 5, False)])
    parts = score_parts([r])
    assert (parts.sorting, parts.recycling, parts.hazards) == (0, 0, 0)
    assert eco_score([r]) == 0


def test_weights_are_50_30_20() -> None:
    # mixed (0.5) -> 25, half recyclable -> 15, no hazards -> 20
    r = rec(quality="mixed", items=[("plastic", 1, True), ("organic", 1, False)])
    parts = score_parts([r])
    assert (parts.sorting, parts.recycling, parts.hazards) == (25, 15, 20)
    assert eco_score([r]) == 60


def test_recyclable_share_is_by_quantity_not_rows() -> None:
    r = rec(items=[("metal", 9, True), ("organic", 1, False)])
    assert score_parts([r]).recycling == 27.0


def test_zero_quantity_bag_does_not_divide_by_zero() -> None:
    r = rec(items=[])
    assert score_parts([r]).recycling == 0
    assert compute_stats([r], NOW).recyclableShare is None


def test_hazards_packed_separately_count_as_safe() -> None:
    separated = rec(quality="good", hazards=["battery"], items=[("e_waste", 1, True)])
    mixed_in = rec(code="ECO-BBBB-BB", quality="mixed", hazards=["battery"], items=[("e_waste", 1, True)])
    assert score_parts([separated]).hazards == 20
    assert score_parts([mixed_in]).hazards == 0
    assert score_parts([separated, mixed_in]).hazards == 10


def test_score_is_clamped_and_rounded() -> None:
    records = [rec(code=f"ECO-{i:04d}-AA", quality=q) for i, q in enumerate(["good", "good", "mixed"])]
    assert 0 <= eco_score(records) <= 100
    assert isinstance(eco_score(records), int)


# --- points ---


def test_points_per_bag() -> None:
    assert [e.points for e in awards_for(rec(quality="mixed"))] == [POINTS_BAG]
    assert [e.reason for e in awards_for(rec(quality="good"))] == ["bag_processed", "good_segregation"]


def test_hazard_bonus_only_when_packed_separately() -> None:
    good = awards_for(rec(quality="good", hazards=["battery"]))
    assert [e.reason for e in good] == ["bag_processed", "good_segregation", "hazards_separated"]
    assert sum(e.points for e in good) == 20
    poor = awards_for(rec(quality="poor", hazards=["battery"]))
    assert [e.reason for e in poor] == ["bag_processed"]


def test_ledger_ids_are_deterministic() -> None:
    assert [e.id for e in awards_for(rec(code="ECO-XYZW-23"))] == ["ECO-XYZW-23-bag_processed", "ECO-XYZW-23-good_segregation"]
    assert awards_for(rec()) == awards_for(rec())


# --- aggregation ---


def test_compute_stats_aggregates_categories_segregation_hazards_and_trend() -> None:
    records = [
        rec("ECO-AAAA-AA", "good", [], [("plastic", 3, True), ("glass", 1, True)], pickup="p1", date="2026-03-01"),
        rec("ECO-BBBB-BB", "poor", ["battery", "sharp"], [("organic", 2, False)], pickup="p1", date="2026-03-01"),
        rec("ECO-CCCC-CC", "mixed", ["battery"], [("plastic", 1, False)], pickup="p2", date="2026-03-08"),
        rec("ECO-DDDD-DD", status="draft"),  # ignored
    ]
    stats = compute_stats(records, NOW)
    assert stats.bagsProcessed == 3 and stats.pickupsProcessed == 2
    assert stats.categories["plastic"].quantity == 4 and stats.categories["plastic"].items == 2
    assert stats.categories["glass"].quantity == 1
    assert stats.totalQuantity == 7 and stats.recyclableQuantity == 4
    assert stats.recyclableShare == round(4 / 7, 3)
    assert stats.segregation == {"good": 1, "mixed": 1, "poor": 1}
    assert stats.hazards == {"battery": 2, "sharp": 1}
    assert (stats.hazardBags, stats.safeHazardBags) == (2, 0)
    assert stats.points == 10 + 5 + 10 + 10
    assert [p.pickupId for p in stats.byPickup] == ["p1", "p2"]
    assert stats.byPickup[0].bags == 2
    assert set(stats.categories) >= {"plastic", "paper_cardboard", "e_waste", "other"}


def test_stats_hash_changes_with_data_not_time() -> None:
    a = compute_stats([rec()], NOW)
    b = compute_stats([rec()], datetime(2027, 1, 1, tzinfo=UTC))
    c = compute_stats([rec(), rec(code="ECO-EEEE-EE")], NOW)
    assert a.statsHash == b.statsHash == stats_hash(a)
    assert a.statsHash != c.statsHash


def test_tips_payload_has_only_aggregates() -> None:
    r = rec(items=[("plastic", 2, True)])
    r.finalItems[0].brand = "SecretBrand"
    payload = tips_payload(compute_stats([r], NOW))
    text = str(payload)
    assert "SecretBrand" not in text and "plastic thing" not in text and "ECO-" not in text and "h1" not in text
    assert payload["quantityByCategory"] == {"plastic": 2}


@pytest.mark.parametrize("quality", ["good", "mixed", "poor"])
def test_trend_points_have_their_own_score(quality: str) -> None:
    stats = compute_stats([rec(quality=quality)], NOW)
    assert stats.byPickup[0].ecoScore == stats.ecoScore
