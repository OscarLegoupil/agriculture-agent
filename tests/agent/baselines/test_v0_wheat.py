"""Tests for baseline v0 (pure wheat loop)."""

from __future__ import annotations

from pathlib import Path

from kaggle_environments import make

from kaggriculture.agent.baselines.v0_wheat import agent as v0_wheat
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


def test_v0_earns_money_over_240_turns() -> None:
    env = make("kaggriculture", configuration={"episodeSteps": 240, "seed": 0})
    env.run([v0_wheat, "pass"])
    v0_reward = env.steps[-1][0].reward
    assert v0_reward is not None
    assert v0_reward > 3000.0  # Started with 3000; must be profitable.


def test_v0_beats_pass_over_five_full_seasons() -> None:
    results = run_pairing(
        V0_PATH,
        "pass",
        seeds=[0, 1, 2, 3, 4],
        workers=1,
        swap_seats=True,
        config={"episodeSteps": 720},
    )
    stats = summarize(results)
    assert stats["wins_a"] > stats["wins_b"], stats
    # v0 vs pass at N=10 should be significant.
    p = sign_test_two_sided(stats["wins_a"], stats["wins_b"])
    assert p < 0.05, f"v0 vs pass sign-test p={p}"


def test_v0_agent_module_is_kaggle_loadable() -> None:
    # The file must be independently executable via kaggle-environments loader.
    env = make("kaggriculture", configuration={"episodeSteps": 96, "seed": 1})
    env.run([V0_PATH, "pass"])
    assert env.steps[-1][0].status == "DONE"
    assert env.steps[-1][0].reward is not None
