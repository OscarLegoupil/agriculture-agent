"""Tests for baseline v3 (v2 plus market-responsive selling and fertilizer reuse)."""

from __future__ import annotations

from pathlib import Path

from kaggle_environments import make

from kaggriculture.agent.baselines.v3_market import agent as v3_market
from kaggriculture.eval import run_pairing, summarize
from kaggriculture.eval.stats import sign_test_two_sided

_BASELINES = Path(__file__).resolve().parents[3] / "src" / "kaggriculture" / "agent" / "baselines"
V2_PATH = str(_BASELINES / "v2_animals.py")
V3_PATH = str(_BASELINES / "v3_market.py")


def test_v3_earns_more_than_v2_over_a_full_season() -> None:
    env = make("kaggriculture", configuration={"episodeSteps": 720, "seed": 0})
    env.run([v3_market, "pass"])
    v3_reward = env.steps[-1][0].reward
    assert v3_reward is not None
    assert v3_reward > 7500.0  # v3 clears ~8000 vs pass at seed 0.


def test_v3_beats_v2_over_five_seeded_seasons() -> None:
    results = run_pairing(
        V3_PATH,
        V2_PATH,
        seeds=[0, 1, 2, 3, 4],
        workers=1,
        swap_seats=True,
        config={"episodeSteps": 720},
    )
    stats = summarize(results)
    assert stats["wins_a"] > stats["wins_b"], stats
    p = sign_test_two_sided(stats["wins_a"], stats["wins_b"])
    assert p < 0.05, f"v3 vs v2 sign-test p={p}"


def test_v3_kaggle_loadable() -> None:
    env = make("kaggriculture", configuration={"episodeSteps": 96, "seed": 1})
    env.run([V3_PATH, "pass"])
    assert env.steps[-1][0].status == "DONE"
    assert env.steps[-1][0].reward is not None
