"""Tests for `kaggriculture.planning.feed_budget`."""

from __future__ import annotations

import pytest

from kaggriculture.planning.feed_budget import (
    AnimalPlan,
    daily_wheat_demand,
    feed_budget,
)


def test_daily_demand_empty_roster_is_zeros() -> None:
    demand = daily_wheat_demand([], season_days=5)
    assert demand == (0, 0, 0, 0, 0, 0)


def test_daily_demand_starts_day_after_purchase() -> None:
    demand = daily_wheat_demand([AnimalPlan("GOOSE", purchase_day=0)], season_days=3)
    assert demand == (0, 1, 1, 1)


def test_daily_demand_accumulates_multiple_animals() -> None:
    roster = [
        AnimalPlan("GOOSE", purchase_day=0),
        AnimalPlan("COW", purchase_day=2),
        AnimalPlan("SHEEP", purchase_day=2, count=2),
    ]
    demand = daily_wheat_demand(roster, season_days=4)
    # day 0: none, day 1: 1 (goose), day 2: 1 (goose still, cow/sheep bought), days 3-4: 1+1+2 = 4.
    assert demand == (0, 1, 1, 4, 4)


def test_daily_demand_ignores_purchases_past_season() -> None:
    demand = daily_wheat_demand([AnimalPlan("GOOSE", purchase_day=100)], season_days=5)
    assert demand == (0, 0, 0, 0, 0, 0)


def test_daily_demand_rejects_negative_season() -> None:
    with pytest.raises(ValueError):
        daily_wheat_demand([], season_days=-1)


def test_animal_plan_rejects_zero_count() -> None:
    with pytest.raises(ValueError):
        AnimalPlan("GOOSE", purchase_day=0, count=0)


def test_animal_plan_rejects_negative_purchase_day() -> None:
    with pytest.raises(ValueError):
        AnimalPlan("GOOSE", purchase_day=-1)


def test_feed_budget_reports_peak_and_total() -> None:
    roster = [
        AnimalPlan("GOOSE", purchase_day=0),
        AnimalPlan("COW", purchase_day=6),
    ]
    budget = feed_budget(roster, season_days=10)
    # goose feeds days 1-10 (10 wheat); cow feeds days 7-10 (4 wheat). Peak: 2.
    assert budget.peak_daily_demand == 2
    assert budget.total_wheat == 10 + 4
    assert budget.target_daily_harvest == 2


def test_feed_budget_tiles_needed_uses_wheat_yield() -> None:
    # Watered-only wheat yields 4 units over 4 days = 1 unit/tile/day.
    # Peak demand 3 -> 3 tiles.
    roster = [AnimalPlan("GOOSE", purchase_day=0, count=3)]
    budget = feed_budget(roster, season_days=5, wheat_watered=True, wheat_fertilized=False)
    assert budget.peak_daily_demand == 3
    assert budget.tiles_needed == 3
    assert budget.wheat_lifecycle_units == 4
    assert budget.wheat_lifecycle_days == 4


def test_feed_budget_fertilized_reduces_tile_count() -> None:
    # Fertilized wheat yields 6 units over 4 days = 1.5 unit/tile/day, so 3 wheat/day
    # needs ceil(3/1.5) = 2 tiles.
    roster = [AnimalPlan("GOOSE", purchase_day=0, count=3)]
    budget = feed_budget(roster, season_days=5, wheat_fertilized=True)
    assert budget.tiles_needed == 2


def test_feed_budget_zero_roster_needs_zero_tiles() -> None:
    budget = feed_budget([], season_days=10)
    assert budget.peak_daily_demand == 0
    assert budget.total_wheat == 0
    assert budget.tiles_needed == 0
