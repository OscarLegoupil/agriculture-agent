"""Tests for the parallel episode runner."""

from __future__ import annotations

from pathlib import Path

from kaggriculture.eval import EpisodeResult, run_episode, run_pairing, summarize


def test_run_episode_pass_vs_pass_terminates_at_starting_money() -> None:
    r = run_episode("pass", "pass", seed=0, config={"episodeSteps": 240})
    assert r.statuses == ("DONE", "DONE")
    # Both agents did nothing; both should still hold their starting money.
    assert r.rewards[0] == r.rewards[1] == 3000.0
    assert r.winner is None


def test_run_episode_is_seed_deterministic() -> None:
    a = run_episode("pass", "starter", seed=42, config={"episodeSteps": 240})
    b = run_episode("pass", "starter", seed=42, config={"episodeSteps": 240})
    assert a.rewards == b.rewards
    assert a.winner == b.winner


def test_swap_seats_flips_seat_0_but_preserves_seed() -> None:
    a = run_episode("pass", "starter", seed=1, seat_0="a", config={"episodeSteps": 240})
    b = run_episode("pass", "starter", seed=1, seat_0="b", config={"episodeSteps": 240})
    assert a.seat_0 == "a"
    assert b.seat_0 == "b"
    # seat_0="a" puts pass in seat 0; seat_0="b" puts starter in seat 0.
    assert a.reward_a == a.rewards[0]
    assert b.reward_a == b.rewards[1]


def test_run_pairing_with_swap_seats_doubles_result_count() -> None:
    seeds = [0, 1, 2]
    results = run_pairing(
        "pass",
        "starter",
        seeds=seeds,
        workers=1,
        swap_seats=True,
        config={"episodeSteps": 96},
    )
    assert len(results) == 2 * len(seeds)
    assert all(isinstance(r, EpisodeResult) for r in results)
    seats = {(r.seed, r.seat_0) for r in results}
    assert seats == {(s, seat) for s in seeds for seat in ("a", "b")}


def test_summarize_reports_win_counts() -> None:
    # Craft synthetic results: 2 wins for a, 1 for b, 1 tie.
    results = [
        EpisodeResult("a", "b", 0, "a", (100.0, 50.0), ("DONE", "DONE"), 0.1),
        EpisodeResult("a", "b", 1, "a", (30.0, 40.0), ("DONE", "DONE"), 0.1),
        EpisodeResult("a", "b", 2, "a", (10.0, 10.0), ("DONE", "DONE"), 0.1),
        EpisodeResult("a", "b", 3, "b", (5.0, 20.0), ("DONE", "DONE"), 0.1),
    ]
    stats = summarize(results)
    assert stats["n"] == 4
    assert stats["wins_a"] == 2
    assert stats["wins_b"] == 1
    assert stats["ties"] == 1
    assert stats["win_rate_a"] == 0.5


def test_replay_dir_writes_json(tmp_path: Path) -> None:
    r = run_episode(
        "pass",
        "pass",
        seed=0,
        config={"episodeSteps": 48},
        replay_dir=tmp_path,
    )
    assert r.replay_path is not None
    replay_file = Path(r.replay_path)
    assert replay_file.exists()
    assert replay_file.stat().st_size > 0
