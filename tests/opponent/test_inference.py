"""Tests for `kaggriculture.opponent.inference`."""

from __future__ import annotations

import pytest
from kaggle_environments import make

from kaggriculture.env.constants import PRODUCTS
from kaggriculture.env.observation import Observation
from kaggriculture.opponent.inference import (
    CommodityEstimate,
    OpponentInventoryTracker,
    town_consumption_between,
)


def test_commodity_estimate_rejects_negative_lower_bound() -> None:
    with pytest.raises(ValueError):
        CommodityEstimate(
            estimate=0.0, lower_bound=-1, upper_bound=0, uncertainty_width=1, floor_risk=0.0
        )


def test_commodity_estimate_rejects_upper_below_lower() -> None:
    with pytest.raises(ValueError):
        CommodityEstimate(
            estimate=0.0, lower_bound=5, upper_bound=3, uncertainty_width=-2, floor_risk=0.0
        )


def test_commodity_estimate_rejects_bad_width() -> None:
    with pytest.raises(ValueError):
        CommodityEstimate(
            estimate=0.0, lower_bound=1, upper_bound=3, uncertainty_width=5, floor_risk=0.0
        )


def test_commodity_estimate_rejects_bad_floor_risk() -> None:
    with pytest.raises(ValueError):
        CommodityEstimate(
            estimate=0.0, lower_bound=0, upper_bound=0, uncertainty_width=0, floor_risk=1.5
        )


def test_town_consumption_between_empty_range_returns_zeroes() -> None:
    out = town_consumption_between(5, 5, unlocked_shops=[])
    assert set(out) == set(PRODUCTS)
    assert all(v == 0 for v in out.values())


def test_town_consumption_rejects_backwards_range() -> None:
    with pytest.raises(ValueError):
        town_consumption_between(10, 5, unlocked_shops=[])


def test_town_consumption_center_fires_at_multiples_of_24() -> None:
    # Range [0, 25) covers steps 0 and 24, both firing the town center.
    out = town_consumption_between(0, 25, unlocked_shops=[])
    for item in PRODUCTS:
        if item == "FERTILIZER":
            assert out[item] == 0
        else:
            assert out[item] == 2


def test_town_consumption_shops_fire_at_multiples_of_4() -> None:
    # Range [0, 5) covers step 0 (shop + town center) and step 4 (shop only).
    out = town_consumption_between(0, 5, unlocked_shops=["PET_CAFE"])
    # PET_CAFE is single-product carrot, multiplier 2, twice = 4. Plus town
    # center consumes 1 carrot at step 0.
    assert out["CARROT"] == 5
    assert out["WHEAT"] == 1  # town center at step 0 only


def test_town_consumption_stacks_multi_step_range() -> None:
    # Range [0, 9) covers steps 0, 4, 8; each fires BAKERY. Step 0 also fires
    # the town center.
    out = town_consumption_between(0, 9, unlocked_shops=["BAKERY"])
    assert out["WHEAT"] == 4  # 3 shop + 1 town center
    assert out["EGG"] == 4


def test_tracker_first_update_leaves_all_estimates_zero() -> None:
    env = make("kaggriculture", configuration={"episodeSteps": 1, "seed": 0})
    env.run(["pass", "pass"])
    obs = Observation.from_dict({**dict(env.steps[0][0].observation), "player": 0})
    tracker = OpponentInventoryTracker()
    est = tracker.update(obs)
    for item in PRODUCTS:
        assert est[item].estimate == 0.0
        assert est[item].lower_bound == 0
        assert est[item].upper_bound == 0


def test_tracker_rejects_bad_config() -> None:
    with pytest.raises(ValueError):
        OpponentInventoryTracker(max_orders_per_turn=0)
    with pytest.raises(ValueError):
        OpponentInventoryTracker(shed_capacity=0)


def _run_and_track(
    agents: list[str], seed: int, steps: int
) -> tuple[list[dict[str, CommodityEstimate]], list[dict[str, int]]]:
    """Run an episode and record per-turn estimates and ground-truth opp holdings."""
    env = make("kaggriculture", configuration={"episodeSteps": steps, "seed": seed})
    env.run(agents)
    tracker = OpponentInventoryTracker()
    estimates_over_time: list[dict[str, CommodityEstimate]] = []
    truth_over_time: list[dict[str, int]] = []
    for step in env.steps:
        obs0_raw = dict(step[0].observation)
        obs0_raw.setdefault("player", 0)
        if "farms" not in obs0_raw:
            continue
        obs0 = Observation.from_dict(obs0_raw)
        est = tracker.update(obs0)
        estimates_over_time.append(est)

        opp_raw = dict(step[1].observation)
        opp_priv = opp_raw.get("private", {}) or {}
        shed = opp_priv.get("shed", {}) or {}
        inventories = opp_priv.get("inventories", []) or []
        total: dict[str, int] = {k: int(shed.get(k, 0)) for k in PRODUCTS}
        for inv in inventories:
            for item, n in inv.items():
                if item in total:
                    total[item] += int(n)
        truth_over_time.append(total)
    return estimates_over_time, truth_over_time


def test_tracker_matches_true_opponent_shed_against_starter() -> None:
    """Starter is a carrot loop with visible sells; the tracker must follow.

    We run pass-vs-starter so opponent is the starter (player 1). The
    bookkeeping identifier is exact when no floor sales happen and no shed
    overflow occurs, so MAE should be zero.
    """
    estimates, truth = _run_and_track(["pass", "starter"], seed=42, steps=240)
    assert len(estimates) == len(truth)
    assert len(estimates) > 10

    for est, tr in zip(estimates, truth, strict=True):
        for item in PRODUCTS:
            assert est[item].estimate == tr[item], f"{item} drift at some step"


def test_tracker_reproduces_low_mae_on_price_stable_commodities() -> None:
    """CARROT, TOMATO, EGG sit far from their price floor at these volumes.

    Dzjiann's identifier reports near-zero MAE for these three commodities on
    self-play episodes. Against the ``random`` opponent, which occasionally
    plants and harvests, the identifier stays exact.
    """
    estimates, truth = _run_and_track(["random", "starter"], seed=7, steps=480)
    for item in ("CARROT", "TOMATO", "EGG"):
        errs = [abs(e[item].estimate - t[item]) for e, t in zip(estimates, truth, strict=True)]
        mae = sum(errs) / len(errs)
        assert mae <= 0.05, f"{item} MAE {mae:.3f} exceeds 0.05"


def test_tracker_widens_slack_when_price_hits_floor() -> None:
    """Floor sales are invisible; the tracker widens the interval each turn
    the market price of a commodity sits at ``PRICE_FLOOR``."""
    env = make("kaggriculture", configuration={"episodeSteps": 1, "seed": 0})
    env.run(["pass", "pass"])
    raw = {**dict(env.steps[0][0].observation), "player": 0}
    obs = Observation.from_dict(raw)
    tracker = OpponentInventoryTracker(max_orders_per_turn=10)
    tracker.update(obs)

    # Fabricate three consecutive floor-price snapshots.
    for offset in range(1, 4):
        r = {**raw}
        r["market"] = {
            "inventory": dict(obs.market.inventory),
            "prices": {**obs.market.prices, "MILK": 1},
        }
        r["hour"] = obs.hour + offset
        r["day"] = obs.day
        est = tracker.update(Observation.from_dict(r))
    # Three consecutive floor turns add 3 * max_orders_per_turn = 30 slack.
    assert est["MILK"].upper_bound - est["MILK"].lower_bound == 30
    assert est["MILK"].floor_risk == 1.0
    assert est["WHEAT"].uncertainty_width == 0
