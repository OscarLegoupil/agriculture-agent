"""Tests for baseline v1 (wheat + carrot mix)."""

from __future__ import annotations

from pathlib import Path

from kaggle_environments import make

from kaggriculture.agent.baselines.v1_mixed import agent as v1_mixed
from kaggriculture.eval import run_pairing, summarize
from kaggriculture.eval.stats import sign_test_two_sided

V0_PATH = str(
    Path(__file__).resolve().parents[3]
    / "src"
    / "kaggriculture"
    / "agent"
    / "baselines"
    / "v0_wheat.py"
)
V1_PATH = str(
    Path(__file__).resolve().parents[3]
    / "src"
    / "kaggriculture"
    / "agent"
    / "baselines"
    / "v1_mixed.py"
)


def test_v1_earns_more_than_v0_over_a_full_season() -> None:
    env = make("kaggriculture", configuration={"episodeSteps": 720, "seed": 0})
    env.run([v1_mixed, "pass"])
    v1_reward = env.steps[-1][0].reward
    assert v1_reward is not None
    assert v1_reward > 4500.0  # v1 clears ~4700 at base prices in this fixed seed.


def test_v1_beats_v0_over_five_seeded_seasons() -> None:
    results = run_pairing(
        V1_PATH,
        V0_PATH,
        seeds=[0, 1, 2, 3, 4],
        workers=1,
        swap_seats=True,
        config={"episodeSteps": 720},
    )
    stats = summarize(results)
    assert stats["wins_a"] > stats["wins_b"], stats
    p = sign_test_two_sided(stats["wins_a"], stats["wins_b"])
    assert p < 0.05, f"v1 vs v0 sign-test p={p}"


def test_v1_kaggle_loadable() -> None:
    env = make("kaggriculture", configuration={"episodeSteps": 96, "seed": 1})
    env.run([V1_PATH, "pass"])
    assert env.steps[-1][0].status == "DONE"
    assert env.steps[-1][0].reward is not None
