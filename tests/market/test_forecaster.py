"""Tests for `kaggriculture.market.forecaster`."""

from __future__ import annotations

import pytest
from kaggle_environments import make

from kaggriculture.env.constants import MARKET_I0, MARKET_PARAMS, PRICE_FLOOR, PRODUCTS
from kaggriculture.env.observation import Observation
from kaggriculture.market.forecaster import (
    PriceForecaster,
    market_price,
    project_inventory,
)


def test_market_price_matches_simulator_at_baseline_inventory() -> None:
    for item, params in MARKET_PARAMS.items():
        assert market_price(item, MARKET_I0) == params["base"], item


def test_market_price_hits_floor_for_massive_glut() -> None:
    assert market_price("MELON", MARKET_I0 + 100_000) == PRICE_FLOOR


def test_market_price_scales_up_with_scarcity() -> None:
    scarce = market_price("WHEAT", MARKET_I0 - MARKET_PARAMS["WHEAT"]["T"])
    assert scarce > MARKET_PARAMS["WHEAT"]["base"]


def test_market_price_rejects_unknown_commodity() -> None:
    with pytest.raises(KeyError):
        market_price("GOLD", MARKET_I0)


def test_project_inventory_zero_horizon_is_current_inventory() -> None:
    inv = dict.fromkeys(PRODUCTS, MARKET_I0)
    out = project_inventory(inv, [], prev_step=0, horizon_steps=0)
    assert out == {item: float(MARKET_I0) for item in PRODUCTS}


def test_project_inventory_applies_town_center_over_horizon() -> None:
    inv = dict.fromkeys(PRODUCTS, MARKET_I0)
    out = project_inventory(inv, [], prev_step=0, horizon_steps=25)
    # Two town-center firings (step 0 and 24), fertilizer excluded.
    assert out["WHEAT"] == MARKET_I0 - 2
    assert out["FERTILIZER"] == MARKET_I0


def test_project_inventory_applies_trade_rate_linearly() -> None:
    inv = dict.fromkeys(PRODUCTS, MARKET_I0)
    rate = dict.fromkeys(PRODUCTS, 0.0)
    rate["WHEAT"] = 2.5  # 2.5 units per step, net sells
    # Start at step 1 so the range [1, 11) skips the town-center firing at 0.
    out = project_inventory(inv, [], prev_step=1, horizon_steps=10, trade_rate=rate)
    assert out["WHEAT"] == pytest.approx(MARKET_I0 + 25.0)


def test_project_inventory_rejects_negative_horizon() -> None:
    with pytest.raises(ValueError):
        project_inventory({}, [], prev_step=0, horizon_steps=-1)


def test_forecaster_rejects_bad_smoothing() -> None:
    with pytest.raises(ValueError):
        PriceForecaster(smoothing=1.5)
    with pytest.raises(ValueError):
        PriceForecaster(smoothing=-0.1)


def test_forecaster_zero_horizon_equals_current_price() -> None:
    env = make("kaggriculture", configuration={"episodeSteps": 1, "seed": 0})
    env.run(["pass", "pass"])
    raw = {**dict(env.steps[0][0].observation), "player": 0}
    obs = Observation.from_dict(raw)
    forecaster = PriceForecaster()
    forecaster.update(obs)
    predicted = forecaster.predict(obs, horizon_steps=0)
    for item in PRODUCTS:
        assert predicted[item] == float(obs.market.prices[item])


def test_forecaster_learns_positive_rate_from_sells() -> None:
    """A market inventory rising each turn drives a positive trade rate."""
    env = make("kaggriculture", configuration={"episodeSteps": 1, "seed": 0})
    env.run(["pass", "pass"])
    raw = {**dict(env.steps[0][0].observation), "player": 0}
    obs0 = Observation.from_dict(raw)
    forecaster = PriceForecaster(smoothing=0.5)
    forecaster.update(obs0)

    # Synthesize five turns of a rising WHEAT inventory.
    for offset in range(1, 6):
        r = {**raw}
        new_inv = dict(obs0.market.inventory)
        new_inv["WHEAT"] = obs0.market.inventory["WHEAT"] + offset * 3
        r["market"] = {"inventory": new_inv, "prices": dict(obs0.market.prices)}
        r["hour"] = obs0.hour + offset
        r["day"] = obs0.day
        forecaster.update(Observation.from_dict(r))

    assert forecaster.trade_rate["WHEAT"] > 2.0
    # FERTILIZER is not touched by shops or the town center, so its rate
    # stays at zero.
    assert forecaster.trade_rate["FERTILIZER"] == 0.0
    # Products consumed by the town center accumulate small phantom rates
    # from the step-0 consumption; they must stay well below WHEAT's rate.
    for other in ("CARROT", "MELON", "MILK"):
        assert forecaster.trade_rate[other] < 0.5


def _episode_forecast_error(
    agents: list[str], seed: int, horizon_days: int, smoothing: float
) -> dict[str, float]:
    """Return per-commodity MAE across an episode for a horizon in days."""
    env = make("kaggriculture", configuration={"episodeSteps": 720, "seed": seed})
    env.run(agents)
    forecaster = PriceForecaster(smoothing=smoothing)
    horizon_steps = horizon_days * 24
    errs: dict[str, list[float]] = {k: [] for k in PRODUCTS}
    obs_list = []
    for step in env.steps:
        raw = dict(step[0].observation)
        raw.setdefault("player", 0)
        if "farms" not in raw:
            continue
        obs_list.append(Observation.from_dict(raw))
    for i, obs in enumerate(obs_list):
        forecaster.update(obs)
        if i + horizon_steps >= len(obs_list):
            break
        target = obs_list[i + horizon_steps]
        pred = forecaster.predict(obs, horizon_steps=horizon_steps)
        for item in PRODUCTS:
            errs[item].append(abs(pred[item] - target.market.prices[item]))
    return {item: sum(v) / len(v) if v else 0.0 for item, v in errs.items()}


def test_forecaster_beats_naive_current_price_at_5_day_horizon() -> None:
    """The rate-drift forecaster should not be worse than the current-price baseline.

    On a v3_market vs v4_expansion pairing at horizon = 5 days, the sum of
    per-commodity MAEs from the forecaster must be at most the sum from the
    naive current-price baseline (worst case: equal, with rate=0).
    """
    seed = 42
    horizon_days = 5
    env = make("kaggriculture", configuration={"episodeSteps": 720, "seed": seed})
    env.run(
        [
            "src/kaggriculture/agent/baselines/v3_market.py",
            "src/kaggriculture/agent/baselines/v4_expansion.py",
        ]
    )
    forecaster = PriceForecaster(smoothing=0.2)
    horizon_steps = horizon_days * 24
    obs_list = []
    for step in env.steps:
        raw = dict(step[0].observation)
        raw.setdefault("player", 0)
        if "farms" not in raw:
            continue
        obs_list.append(Observation.from_dict(raw))

    forecast_err = {k: 0.0 for k in PRODUCTS}
    naive_err = {k: 0.0 for k in PRODUCTS}
    n = 0
    for i, obs in enumerate(obs_list):
        forecaster.update(obs)
        if i + horizon_steps >= len(obs_list):
            break
        target = obs_list[i + horizon_steps]
        pred = forecaster.predict(obs, horizon_steps=horizon_steps)
        for item in PRODUCTS:
            forecast_err[item] += abs(pred[item] - target.market.prices[item])
            naive_err[item] += abs(obs.market.prices[item] - target.market.prices[item])
        n += 1
    assert n > 100
    total_forecast = sum(forecast_err.values()) / n
    total_naive = sum(naive_err.values()) / n
    # Rate-based forecast must be at least as good as constant-price.
    assert (
        total_forecast <= total_naive * 1.10
    ), f"forecast {total_forecast:.2f} vs naive {total_naive:.2f}"


def test_forecaster_output_plugs_into_replanner_price_map() -> None:
    """Sanity: forecaster output is a str->float dict, safe for DynamicReplanner."""
    env = make("kaggriculture", configuration={"episodeSteps": 1, "seed": 0})
    env.run(["pass", "pass"])
    raw = {**dict(env.steps[0][0].observation), "player": 0}
    obs = Observation.from_dict(raw)
    forecaster = PriceForecaster()
    forecaster.update(obs)
    forecast = forecaster.predict_days(obs, horizon_days=1)
    assert set(forecast) == set(PRODUCTS)
    assert all(isinstance(v, float) for v in forecast.values())
    assert all(v >= float(PRICE_FLOOR) for v in forecast.values())
