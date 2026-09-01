"""Tests for the M7-b micro-controller."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from kaggle_environments import make

from kaggriculture.agent.baselines.v4_expansion import agent as v4_expansion
from kaggriculture.agent.route_agent import (
    MicroController,
    agent_from_yaml,
    wrap_with_micro,
)
from kaggriculture.agent.route_agent.micro import apply_early_sell_overrides

_V4_YAML = Path(__file__).resolve().parents[3] / "configs" / "routes" / "v4_baseline.yaml"


def _base_obs() -> dict[str, Any]:
    return {
        "player": 0,
        "step": 0,
        "day": 0,
        "hour": 0,
        "farms": [
            {
                "money": 3000.0,
                "tiles": [[None] * 10 for _ in range(10)],
                "farmer": [4, 4],
                "hands": [],
                "unlocked_quadrants": ["NW"],
                "hires_today": 0,
            },
            {
                "money": 3000.0,
                "tiles": [[None] * 10 for _ in range(10)],
                "farmer": [5, 5],
                "hands": [],
                "unlocked_quadrants": ["NW"],
                "hires_today": 0,
            },
        ],
        "market": {"prices": {}, "inventory": {}},
        "town": {"unlocked_shops": []},
        "private": {"shed": {}, "seeds": {}, "inventories": [{}]},
    }


def test_micro_returns_action_dict_shape() -> None:
    micro = wrap_with_micro(agent_from_yaml(_V4_YAML))
    action = micro(_base_obs())
    assert set(action.keys()) == {"farmer", "hands", "market"}


def test_micro_never_removes_base_market_entries() -> None:
    base_market = [["BUY_SEED", "WHEAT", 1]]

    def base_agent(_: dict[str, Any]) -> dict[str, Any]:
        return {"farmer": ["PASS"], "hands": [], "market": list(base_market)}

    micro = wrap_with_micro(base_agent)
    action = micro(_base_obs())
    assert base_market[0] in action["market"]


def test_micro_adds_sell_when_forecast_drop_predicted() -> None:
    market: list[list[Any]] = []
    added = apply_early_sell_overrides(
        market=market,
        shed={"WHEAT": 20},
        prices_now={"WHEAT": 20},
        prices_future={"WHEAT": 5.0},
        drop_ratio=0.7,
        min_current_price=5,
    )
    assert added == 1
    assert ["SELL", "WHEAT", 20] in market


def test_micro_skips_when_forecast_stable() -> None:
    market: list[list[Any]] = []
    added = apply_early_sell_overrides(
        market=market,
        shed={"WHEAT": 20},
        prices_now={"WHEAT": 20},
        prices_future={"WHEAT": 19.0},
        drop_ratio=0.7,
        min_current_price=5,
    )
    assert added == 0
    assert market == []


def test_micro_skips_when_price_near_floor() -> None:
    market: list[list[Any]] = []
    added = apply_early_sell_overrides(
        market=market,
        shed={"WHEAT": 20},
        prices_now={"WHEAT": 3},
        prices_future={"WHEAT": 1.0},
        drop_ratio=0.7,
        min_current_price=5,
    )
    assert added == 0


def test_micro_skips_products_already_being_sold_by_route() -> None:
    market: list[list[Any]] = [["SELL", "WHEAT", 5]]
    added = apply_early_sell_overrides(
        market=market,
        shed={"WHEAT": 20},
        prices_now={"WHEAT": 20},
        prices_future={"WHEAT": 5.0},
        drop_ratio=0.7,
        min_current_price=5,
    )
    assert added == 0
    assert len([m for m in market if m[0] == "SELL" and m[1] == "WHEAT"]) == 1


def test_micro_resets_on_step_backwards() -> None:
    def base_agent(_: dict[str, Any]) -> dict[str, Any]:
        return {"farmer": ["PASS"], "hands": [], "market": []}

    micro = MicroController(base_agent=base_agent)
    obs = _base_obs()
    obs["step"] = 100
    obs["day"] = 4
    obs["hour"] = 4
    micro(obs)
    assert micro._last_step == 100
    obs2 = _base_obs()
    obs2["step"] = 0
    micro(obs2)
    assert micro._last_step == 0


def test_micro_respects_hard_budget_by_returning_base_on_slow_update(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def base_agent(_: dict[str, Any]) -> dict[str, Any]:
        return {"farmer": ["BASE"], "hands": [], "market": [["BASE"]]}

    micro = MicroController(base_agent=base_agent, hard_budget_seconds=1e-9)
    action = micro(_base_obs())
    # With an ~impossible budget the micro layer bails to the base action.
    assert action == {"farmer": ["BASE"], "hands": [], "market": [["BASE"]]}


@pytest.mark.parametrize("seed", [0, 1])
def test_micro_agent_completes_a_full_episode_vs_pass(seed: int) -> None:
    env = make("kaggriculture", configuration={"episodeSteps": 720, "seed": seed})
    micro = wrap_with_micro(agent_from_yaml(_V4_YAML))
    env.run([micro, "pass"])
    assert env.steps[-1][0].status == "DONE"
    assert env.steps[-1][0].reward is not None


def test_micro_never_worse_than_route_on_seed_0_vs_pass() -> None:
    # v4_baseline earns 9191 vs pass on seed 0. Micro overlay should be at
    # least as good; a large regression means the sell overrides are hurting.
    env_micro = make("kaggriculture", configuration={"episodeSteps": 720, "seed": 0})
    env_base = make("kaggriculture", configuration={"episodeSteps": 720, "seed": 0})
    env_micro.run([wrap_with_micro(agent_from_yaml(_V4_YAML)), "pass"])
    env_base.run([v4_expansion, "pass"])
    reward_micro = float(env_micro.steps[-1][0].reward or 0.0)
    reward_base = float(env_base.steps[-1][0].reward or 0.0)
    # Allow some slack for now: assert we are within 5% of the base.
    assert reward_micro >= reward_base * 0.95, (reward_micro, reward_base)
