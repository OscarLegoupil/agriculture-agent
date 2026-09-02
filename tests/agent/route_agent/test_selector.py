"""Tests for the portfolio route selector."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from kaggle_environments import make

from kaggriculture.agent.route_agent.selector import (
    RouteSelector,
    SelectorSignals,
    build_default_selector,
    default_heuristic,
    portfolio_from_yaml_paths,
)

_CONFIGS = Path(__file__).resolve().parents[3] / "configs" / "routes"


def _dummy_agent(name: str) -> Any:
    def agent(obs: dict[str, Any]) -> dict[str, Any]:
        return {"farmer": [name], "hands": [], "market": []}

    return agent


def test_default_heuristic_prefers_wheat_agg_on_egg_glut() -> None:
    sig = SelectorSignals(
        egg_upper=30,
        milk_upper=0,
        wool_upper=0,
        opponent_has_animal=True,
        opponent_bought_land=False,
    )
    assert default_heuristic(sig) == "v4_wheat_agg"


def test_default_heuristic_prefers_premium_hold_when_opponent_has_no_animal() -> None:
    sig = SelectorSignals(
        egg_upper=0,
        milk_upper=0,
        wool_upper=0,
        opponent_has_animal=False,
        opponent_bought_land=False,
    )
    assert default_heuristic(sig) == "v4_premium_hold"


def test_default_heuristic_prefers_early_tail_when_opponent_bought_land() -> None:
    sig = SelectorSignals(
        egg_upper=0,
        milk_upper=0,
        wool_upper=0,
        opponent_has_animal=True,
        opponent_bought_land=True,
    )
    assert default_heuristic(sig) == "v4_early_tail"


def test_default_heuristic_falls_back_to_early_tail() -> None:
    sig = SelectorSignals(
        egg_upper=0,
        milk_upper=0,
        wool_upper=0,
        opponent_has_animal=True,
        opponent_bought_land=False,
    )
    assert default_heuristic(sig) == "v4_early_tail"


def _base_obs(day: int = 0, hour: int = 0) -> dict[str, Any]:
    inventory = {
        p: 10_000
        for p in (
            "WHEAT",
            "CARROT",
            "TOMATO",
            "STRAWBERRY",
            "MELON",
            "EGG",
            "MILK",
            "WOOL",
            "FERTILIZER",
        )
    }
    return {
        "player": 0,
        "step": day * 24 + hour,
        "day": day,
        "hour": hour,
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
        "market": {"prices": {}, "inventory": inventory},
        "town": {"unlocked_shops": []},
        "private": {"shed": {}, "seeds": {}, "inventories": [{}]},
    }


def test_selector_uses_default_before_decision_day() -> None:
    portfolio = {
        "v4_baseline": _dummy_agent("base"),
        "v4_wheat_agg": _dummy_agent("agg"),
    }
    sel = RouteSelector(portfolio=portfolio, default_key="v4_baseline", decision_day=3)
    action = sel(_base_obs(day=0, hour=5))
    assert action["farmer"] == ["base"]
    assert sel.chosen_key == "v4_baseline"


def test_selector_switches_at_decision_day() -> None:
    portfolio = {
        "v4_baseline": _dummy_agent("base"),
        "v4_wheat_agg": _dummy_agent("agg"),
        "v4_premium_hold": _dummy_agent("prem"),
        "v4_early_tail": _dummy_agent("tail"),
    }

    def force_prem(_: SelectorSignals) -> str:
        return "v4_premium_hold"

    sel = RouteSelector(
        portfolio=portfolio,
        default_key="v4_baseline",
        decision_day=3,
        heuristic=force_prem,
    )
    sel(_base_obs(day=0, hour=0))
    sel(_base_obs(day=1, hour=0))
    sel(_base_obs(day=2, hour=0))
    action = sel(_base_obs(day=3, hour=0))
    assert action["farmer"] == ["prem"]
    assert sel.chosen_key == "v4_premium_hold"
    assert sel.switches == 1


def test_selector_rejects_unknown_default_key() -> None:
    with pytest.raises(KeyError):
        RouteSelector(portfolio={"a": _dummy_agent("a")}, default_key="missing")


def test_selector_resets_on_step_backwards() -> None:
    portfolio = {"v4_baseline": _dummy_agent("base"), "v4_wheat_agg": _dummy_agent("agg")}

    def always_agg(_: SelectorSignals) -> str:
        return "v4_wheat_agg"

    sel = RouteSelector(
        portfolio=portfolio, default_key="v4_baseline", decision_day=1, heuristic=always_agg
    )
    sel(_base_obs(day=0, hour=0))
    sel(_base_obs(day=1, hour=0))
    assert sel.chosen_key == "v4_wheat_agg"
    sel(_base_obs(day=0, hour=0))
    assert sel.chosen_key == "v4_baseline"


def test_portfolio_from_yaml_paths_loads_all() -> None:
    paths = [
        str(_CONFIGS / "v4_baseline.yaml"),
        str(_CONFIGS / "v4_wheat_agg.yaml"),
        str(_CONFIGS / "v4_premium_hold.yaml"),
        str(_CONFIGS / "v4_early_tail.yaml"),
    ]
    portfolio = portfolio_from_yaml_paths(paths)
    assert set(portfolio.keys()) == {
        "v4_baseline",
        "v4_wheat_agg",
        "v4_premium_hold",
        "v4_early_tail",
    }


def test_full_selector_agent_completes_episode() -> None:
    paths = [
        str(_CONFIGS / "v4_baseline.yaml"),
        str(_CONFIGS / "v4_wheat_agg.yaml"),
        str(_CONFIGS / "v4_premium_hold.yaml"),
        str(_CONFIGS / "v4_early_tail.yaml"),
    ]
    portfolio = portfolio_from_yaml_paths(paths)
    agent = build_default_selector(portfolio, default_key="v4_baseline")
    env = make("kaggriculture", configuration={"episodeSteps": 720, "seed": 0})
    env.run([agent, "pass"])
    assert env.steps[-1][0].status == "DONE"
    assert env.steps[-1][0].reward is not None
    assert env.steps[-1][0].reward > 5000
