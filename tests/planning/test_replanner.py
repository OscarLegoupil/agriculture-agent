"""Tests for `kaggriculture.planning.replanner`."""

from __future__ import annotations

import pytest

from kaggriculture.env.constants import MARKET_PARAMS
from kaggriculture.planning.replanner import (
    DynamicReplanner,
    ReplanEvent,
    max_relative_deviation,
)


def _base_prices() -> dict[str, float]:
    return {k: float(v["base"]) for k, v in MARKET_PARAMS.items()}


def test_max_relative_deviation_matches_expected() -> None:
    dev, culprit = max_relative_deviation(
        {"WHEAT": 30.0, "MELON": 250.0}, {"WHEAT": 25.0, "MELON": 250.0}
    )
    assert culprit == "WHEAT"
    assert dev == pytest.approx(0.2)


def test_max_relative_deviation_skips_missing_resources() -> None:
    dev, culprit = max_relative_deviation({"WHEAT": 30.0}, {"MELON": 250.0})
    assert dev == 0.0
    assert culprit is None


def test_max_relative_deviation_treats_zero_forecast_as_full_dev() -> None:
    dev, culprit = max_relative_deviation({"WHEAT": 25.0}, {"WHEAT": 0.0})
    assert dev == 1.0
    assert culprit == "WHEAT"


def test_replanner_initialises_with_static_allocation() -> None:
    planner = DynamicReplanner(tiles=8, season_days=30, initial_forecast=_base_prices())
    assert planner.allocation.tiles == 8
    assert planner.allocation.horizon_days == 30
    assert planner.events == []


def test_replanner_step_does_not_fire_when_prices_stable() -> None:
    planner = DynamicReplanner(
        tiles=8, season_days=30, initial_forecast=_base_prices(), threshold_pct=0.15
    )
    event = planner.step(1, _base_prices())
    assert event is None
    assert planner.events == []


def test_replanner_step_fires_when_price_moves_past_threshold() -> None:
    prices = _base_prices()
    planner = DynamicReplanner(tiles=8, season_days=30, initial_forecast=prices, threshold_pct=0.15)
    shocked = dict(prices)
    shocked["MELON"] = 1.0  # crash melon to force a re-plan.
    event = planner.step(day=2, observed_prices=shocked)
    assert isinstance(event, ReplanEvent)
    assert event.triggering_resource == "MELON"
    assert event.day == 2
    assert event.max_deviation > 0.15
    assert planner.events == [event]


def test_replanner_updates_forecast_after_replan() -> None:
    prices = _base_prices()
    planner = DynamicReplanner(tiles=8, season_days=30, initial_forecast=prices, threshold_pct=0.10)
    shocked = {**prices, "WHEAT": 100.0}
    planner.step(day=1, observed_prices=shocked)
    assert planner.forecast["WHEAT"] == 100.0


def test_replanner_second_stable_step_does_not_double_fire() -> None:
    prices = _base_prices()
    planner = DynamicReplanner(tiles=8, season_days=30, initial_forecast=prices, threshold_pct=0.10)
    shocked = {**prices, "WHEAT": 100.0}
    planner.step(day=1, observed_prices=shocked)
    # Same shock at day 2 should not fire because forecast already absorbed it.
    event = planner.step(day=2, observed_prices=shocked)
    assert event is None
    assert len(planner.events) == 1


def test_replanner_reports_replan_frequency() -> None:
    prices = _base_prices()
    planner = DynamicReplanner(tiles=8, season_days=30, initial_forecast=prices, threshold_pct=0.15)
    planner.step(day=1, observed_prices=prices)
    planner.step(day=2, observed_prices={**prices, "MELON": 1.0})
    planner.step(day=3, observed_prices={**prices, "MELON": 1.0})
    # 1 re-plan over 3 observed days.
    assert planner.replan_frequency == pytest.approx(1 / 3)


def test_replanner_uses_shortened_horizon_on_replan() -> None:
    prices = _base_prices()
    planner = DynamicReplanner(tiles=6, season_days=30, initial_forecast=prices, threshold_pct=0.10)
    planner.step(day=10, observed_prices={**prices, "MELON": 1.0})
    assert planner.allocation.horizon_days == 20


def test_replanner_rejects_bad_threshold() -> None:
    with pytest.raises(ValueError):
        DynamicReplanner(
            tiles=8, season_days=30, initial_forecast=_base_prices(), threshold_pct=-0.1
        )


def test_replanner_step_rejects_day_beyond_season() -> None:
    planner = DynamicReplanner(tiles=8, season_days=30, initial_forecast=_base_prices())
    with pytest.raises(ValueError):
        planner.step(day=31, observed_prices=_base_prices())
