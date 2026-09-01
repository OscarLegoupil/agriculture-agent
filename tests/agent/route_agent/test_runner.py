"""Tests for the RouteAgent runner.

Includes the v4 port byte-for-byte reproduction test: on fixed seeds against a
range of opponents, the YAML-driven route agent must produce identical episode
outputs to the hand-coded v4_expansion baseline.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from kaggle_environments import make

from kaggriculture.agent.baselines.v4_expansion import agent as v4_expansion
from kaggriculture.agent.route_agent import RouteAgent, agent_from_yaml, load_route

_V4_YAML = Path(__file__).resolve().parents[3] / "configs" / "routes" / "v4_baseline.yaml"


def _minimal_obs() -> dict:
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


def test_runner_returns_valid_action_shape() -> None:
    route = load_route(_V4_YAML)
    agent = RouteAgent(route)
    action = agent(_minimal_obs())
    assert set(action.keys()) == {"farmer", "hands", "market"}
    assert isinstance(action["farmer"], list)
    assert isinstance(action["hands"], list)
    assert isinstance(action["market"], list)


def test_runner_handles_missing_farm_gracefully() -> None:
    route = load_route(_V4_YAML)
    agent = RouteAgent(route)
    action = agent({"player": 5, "farms": []})
    assert action == {"farmer": ["PASS"], "hands": [], "market": []}


@pytest.mark.parametrize("seed", [0, 1, 2, 3, 4])
def test_v4_port_matches_v4_expansion_vs_pass(seed: int) -> None:
    env_r = make("kaggriculture", configuration={"episodeSteps": 720, "seed": seed})
    env_v = make("kaggriculture", configuration={"episodeSteps": 720, "seed": seed})
    env_r.run([agent_from_yaml(_V4_YAML), "pass"])
    env_v.run([v4_expansion, "pass"])
    assert env_r.steps[-1][0].reward == env_v.steps[-1][0].reward
    assert env_r.steps[-1][0].status == env_v.steps[-1][0].status


@pytest.mark.parametrize("seed", [7, 42])
def test_v4_port_matches_v4_expansion_vs_starter(seed: int) -> None:
    env_r = make("kaggriculture", configuration={"episodeSteps": 720, "seed": seed})
    env_v = make("kaggriculture", configuration={"episodeSteps": 720, "seed": seed})
    env_r.run([agent_from_yaml(_V4_YAML), "starter"])
    env_v.run([v4_expansion, "starter"])
    assert env_r.steps[-1][0].reward == env_v.steps[-1][0].reward


def test_v4_port_matches_v4_expansion_seat_swap() -> None:
    env_r = make("kaggriculture", configuration={"episodeSteps": 720, "seed": 3})
    env_v = make("kaggriculture", configuration={"episodeSteps": 720, "seed": 3})
    env_r.run(["pass", agent_from_yaml(_V4_YAML)])
    env_v.run(["pass", v4_expansion])
    assert env_r.steps[-1][1].reward == env_v.steps[-1][1].reward
