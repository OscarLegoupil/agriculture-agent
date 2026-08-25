"""Tests for baseline v2 (v1 plus a fed and cared goose)."""

from __future__ import annotations

from pathlib import Path

from kaggle_environments import make

from kaggriculture.agent.baselines.v2_animals import agent as v2_animals
from kaggriculture.eval import run_pairing, summarize
from kaggriculture.eval.stats import sign_test_two_sided

_BASELINES = Path(__file__).resolve().parents[3] / "src" / "kaggriculture" / "agent" / "baselines"
V1_PATH = str(_BASELINES / "v1_mixed.py")
V2_PATH = str(_BASELINES / "v2_animals.py")


def test_v2_earns_more_than_v1_over_a_full_season() -> None:
    env = make("kaggriculture", configuration={"episodeSteps": 720, "seed": 0})
    env.run([v2_animals, "pass"])
    v2_reward = env.steps[-1][0].reward
    assert v2_reward is not None
    assert v2_reward > 5500.0  # v2 clears ~5900 vs pass at seed 0.


def test_v2_beats_v1_over_five_seeded_seasons() -> None:
    results = run_pairing(
        V2_PATH,
        V1_PATH,
        seeds=[0, 1, 2, 3, 4],
        workers=1,
        swap_seats=True,
        config={"episodeSteps": 720},
    )
    stats = summarize(results)
    assert stats["wins_a"] > stats["wins_b"], stats
    p = sign_test_two_sided(stats["wins_a"], stats["wins_b"])
    assert p < 0.05, f"v2 vs v1 sign-test p={p}"


def test_v2_kaggle_loadable() -> None:
    env = make("kaggriculture", configuration={"episodeSteps": 96, "seed": 1})
    env.run([V2_PATH, "pass"])
    assert env.steps[-1][0].status == "DONE"
    assert env.steps[-1][0].reward is not None
