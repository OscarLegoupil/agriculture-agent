"""Tests for baseline v4 (v3 plus a second carrot tile and one hired hand)."""

from __future__ import annotations

from pathlib import Path

from kaggle_environments import make

from kaggriculture.agent.baselines.v4_expansion import agent as v4_expansion
from kaggriculture.eval import run_pairing, summarize
from kaggriculture.eval.stats import sign_test_two_sided

_BASELINES = Path(__file__).resolve().parents[3] / "src" / "kaggriculture" / "agent" / "baselines"
V3_PATH = str(_BASELINES / "v3_market.py")
V4_PATH = str(_BASELINES / "v4_expansion.py")


def test_v4_earns_more_than_v3_over_a_full_season() -> None:
    env = make("kaggriculture", configuration={"episodeSteps": 720, "seed": 0})
    env.run([v4_expansion, "pass"])
    v4_reward = env.steps[-1][0].reward
    assert v4_reward is not None
    assert v4_reward > 8000.0


def test_v4_beats_v3_over_five_seeded_seasons() -> None:
    results = run_pairing(
        V4_PATH,
        V3_PATH,
        seeds=[0, 1, 2, 3, 4],
        workers=1,
        swap_seats=True,
        config={"episodeSteps": 720},
    )
    stats = summarize(results)
    assert stats["wins_a"] > stats["wins_b"], stats
    p = sign_test_two_sided(stats["wins_a"], stats["wins_b"])
    assert p < 0.05, f"v4 vs v3 sign-test p={p}"


def test_v4_kaggle_loadable() -> None:
    env = make("kaggriculture", configuration={"episodeSteps": 96, "seed": 1})
    env.run([V4_PATH, "pass"])
    assert env.steps[-1][0].status == "DONE"
    assert env.steps[-1][0].reward is not None
