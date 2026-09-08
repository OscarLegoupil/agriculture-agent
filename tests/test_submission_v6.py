"""Checks on the packaged v6 submission.

The submission is a hand-transcribed copy of the scheduler and the shipped
route, so the load-bearing test is that it reproduces the package agent's
rewards exactly on fixed seeds. Anything that drifts between the two shows up
there.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from kaggle_environments import make

from kaggriculture.agent.route_agent import agent_from_yaml

_REPO = Path(__file__).resolve().parents[1]
_V6 = _REPO / "submissions" / "20260908-v6" / "main.py"
_V5 = _REPO / "submissions" / "20260902-v5" / "main.py"
_ROUTE = _REPO / "configs" / "routes" / "tuned" / "generated_expansion.yaml"


@pytest.mark.parametrize("opponent", ["pass", "starter"])
def test_v6_completes_720_turn_episode(opponent: str) -> None:
    env = make("kaggriculture", configuration={"episodeSteps": 720, "seed": 42})
    env.run([str(_V6), opponent])
    assert env.steps[-1][0].status == "DONE"
    assert env.steps[-1][0].reward is not None
    assert env.steps[-1][0].reward > 20_000


@pytest.mark.parametrize("seed", [0, 7])
def test_v6_matches_the_package_route_agent(seed: int) -> None:
    packaged = make("kaggriculture", configuration={"episodeSteps": 720, "seed": seed})
    packaged.run([str(_V6), "starter"])
    from_yaml = make("kaggriculture", configuration={"episodeSteps": 720, "seed": seed})
    from_yaml.run([agent_from_yaml(_ROUTE), "starter"])
    assert packaged.steps[-1][0].reward == from_yaml.steps[-1][0].reward


def test_v6_beats_v5_on_a_paired_seed() -> None:
    env = make("kaggriculture", configuration={"episodeSteps": 720, "seed": 0})
    env.run([str(_V6), str(_V5)])
    r_a = float(env.steps[-1][0].reward or 0.0)
    r_b = float(env.steps[-1][1].reward or 0.0)
    assert r_a > r_b, (r_a, r_b)


def test_v6_survives_a_malformed_observation() -> None:
    import importlib.util

    spec = importlib.util.spec_from_file_location("submission_v6", _V6)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert module.agent({}) == {"farmer": ["PASS"], "hands": [], "market": []}
    assert module.agent({"player": 5, "farms": []}) == {
        "farmer": ["PASS"],
        "hands": [],
        "market": [],
    }
