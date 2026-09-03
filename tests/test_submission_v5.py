"""Smoke test: the v5 submission agent loads and completes an episode.

Also runs a quick paired A/B vs v4 to confirm the packaged agent is not
regression-tested silently.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from kaggle_environments import make

_REPO = Path(__file__).resolve().parents[1]
_V5 = _REPO / "submissions" / "20260902-v5" / "main.py"
_V4 = _REPO / "submissions" / "20260825-v4" / "main.py"


@pytest.mark.parametrize("opponent", ["pass", "starter"])
def test_v5_completes_720_turn_episode(opponent: str) -> None:
    env = make("kaggriculture", configuration={"episodeSteps": 720, "seed": 42})
    env.run([str(_V5), opponent])
    assert env.steps[-1][0].status == "DONE"
    assert env.steps[-1][0].reward is not None
    assert env.steps[-1][0].reward > 5000


def test_v5_still_beats_v4_on_a_paired_seed() -> None:
    env = make("kaggriculture", configuration={"episodeSteps": 720, "seed": 0})
    env.run([str(_V5), str(_V4)])
    r_a = float(env.steps[-1][0].reward or 0.0)
    r_b = float(env.steps[-1][1].reward or 0.0)
    assert r_a > r_b, (r_a, r_b)
