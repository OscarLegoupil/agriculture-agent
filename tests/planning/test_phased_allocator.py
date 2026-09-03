"""Tests for `kaggriculture.planning.phased_allocator`."""

from __future__ import annotations

import pytest

from kaggriculture.planning.phased_allocator import (
    OverSubscription,
    Phase,
    PhasedPlan,
    assert_worker_capacity,
    build_phased_plan,
    validate_worker_capacity,
)


def test_single_phase_no_land_buys_no_hire() -> None:
    plan = build_phased_plan(season_days=30)
    assert plan.season_days == 30
    assert len(plan.phases) == 1
    phase = plan.phases[0]
    assert phase.start_day == 0
    assert phase.end_day == 30
    assert phase.tiles == 25  # NW only
    assert phase.hands == 0
    assert phase.land_buys == ()


def test_land_buy_splits_into_two_phases_with_tile_jump() -> None:
    plan = build_phased_plan(season_days=30, land_buy_days={"NE": 10})
    assert len(plan.phases) == 2
    first, second = plan.phases
    assert (first.start_day, first.end_day) == (0, 10)
    assert first.tiles == 25
    assert (second.start_day, second.end_day) == (10, 30)
    assert second.tiles == 50
    assert len(second.land_buys) == 1
    assert second.land_buys[0].quadrant == "NE"
    assert second.land_buys[0].day == 10
    assert second.land_buys[0].cost == 1000


def test_multiple_land_buys_and_hire_ramp_produce_expected_boundaries() -> None:
    plan = build_phased_plan(
        season_days=30,
        land_buy_days={"NE": 4, "SW": 10},
        hire_ramp={0: 1, 5: 3},
    )
    boundaries = [p.start_day for p in plan.phases] + [plan.phases[-1].end_day]
    assert boundaries == [0, 4, 5, 10, 30]

    tiles_by_phase = [p.tiles for p in plan.phases]
    assert tiles_by_phase == [25, 50, 50, 75]

    hands_by_phase = [p.hands for p in plan.phases]
    assert hands_by_phase == [1, 1, 3, 3]


def test_phase_land_buys_attached_only_to_the_phase_they_start() -> None:
    plan = build_phased_plan(season_days=20, land_buy_days={"NE": 5, "SW": 12})
    all_land_buys = [lb for phase in plan.phases for lb in phase.land_buys]
    assert {(lb.quadrant, lb.day) for lb in all_land_buys} == {("NE", 5), ("SW", 12)}
    # Each land buy shows up in exactly one phase.
    assert len(all_land_buys) == 2


def test_land_buy_day_zero_folds_into_first_phase() -> None:
    plan = build_phased_plan(season_days=30, land_buy_days={"NE": 0})
    assert len(plan.phases) == 1
    assert plan.phases[0].tiles == 50


def test_rejects_land_buy_skipping_a_quadrant() -> None:
    with pytest.raises(ValueError):
        build_phased_plan(season_days=30, land_buy_days={"SW": 5})


def test_rejects_land_buys_out_of_order_days() -> None:
    with pytest.raises(ValueError):
        build_phased_plan(season_days=30, land_buy_days={"NE": 10, "SW": 5})


def test_rejects_unknown_quadrant() -> None:
    with pytest.raises(ValueError):
        build_phased_plan(season_days=30, land_buy_days={"NORTH_POLE": 1})


def test_rejects_negative_hire_ramp_day() -> None:
    with pytest.raises(ValueError):
        build_phased_plan(season_days=30, hire_ramp={-1: 2})


def test_rejects_negative_hire_ramp_target() -> None:
    with pytest.raises(ValueError):
        build_phased_plan(season_days=30, hire_ramp={0: -1})


def test_rejects_non_positive_season_days() -> None:
    with pytest.raises(ValueError):
        build_phased_plan(season_days=0)


def test_worker_tile_demand_and_capacity_properties() -> None:
    plan = build_phased_plan(
        season_days=30,
        land_buy_days={"NE": 5},
        hire_ramp={0: 2},
    )
    phase = plan.phases[0]
    assert phase.worker_capacity == (1 + 2) * 8
    assert phase.worker_tile_demand == (
        phase.allocation.fill_crop_tiles
        + phase.allocation.wheat_tiles
        + phase.allocation.structure_tiles
    )


def test_daily_hire_cost_matches_fib_sum() -> None:
    plan = build_phased_plan(season_days=30, hire_ramp={0: 4})
    # fib(0)=1, fib(1)=1, fib(2)=2, fib(3)=3 -> sum = 7
    assert plan.phases[0].daily_hire_cost == 7


def test_daily_hire_cost_zero_hands_is_zero() -> None:
    plan = build_phased_plan(season_days=30)
    assert plan.phases[0].daily_hire_cost == 0


def test_validate_worker_capacity_passes_for_small_footprint() -> None:
    plan = build_phased_plan(
        season_days=30,
        land_buy_days={"NE": 5},
        hire_ramp={0: 7},
    )
    assert validate_worker_capacity(plan) == []
    assert_worker_capacity(plan)  # must not raise


def test_validate_worker_capacity_flags_over_subscribed_phase() -> None:
    # 75 tiles unlocked from day 0, zero hands: solo farmer capacity is 8
    # tiles/day, so a full 3-quadrant footprint massively over-subscribes.
    plan = build_phased_plan(
        season_days=30,
        land_buy_days={"NE": 0, "SW": 0},
        hire_ramp={0: 0},
    )
    violations = validate_worker_capacity(plan)
    assert len(violations) == 1
    violation = violations[0]
    assert isinstance(violation, OverSubscription)
    assert violation.phase_index == 0
    assert violation.capacity == 8
    assert violation.demand > violation.capacity

    with pytest.raises(ValueError):
        assert_worker_capacity(plan)


def test_phase_dataclass_is_frozen_and_typed() -> None:
    plan = build_phased_plan(season_days=30)
    assert isinstance(plan, PhasedPlan)
    assert isinstance(plan.phases[0], Phase)
    with pytest.raises(AttributeError):
        plan.phases[0].tiles = 999  # type: ignore[misc]


def test_price_map_and_animal_caps_forwarded_to_underlying_allocator() -> None:
    plan = build_phased_plan(
        season_days=30,
        price_map={"MELON": 1.0, "STRAWBERRY": 1.0, "TOMATO": 1.0, "CARROT": 1.0},
        max_animals_per_species={"GOOSE": 4, "COW": 0, "SHEEP": 0},
    )
    phase = plan.phases[0]
    assert phase.allocation.animal_counts.get("GOOSE", 0) > 0
