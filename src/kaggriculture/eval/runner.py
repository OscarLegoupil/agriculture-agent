"""Parallel deterministic episode runner.

Runs pairings of two named agents across a fixed seed set, optionally swapping
seats to average out the measured seat-0 advantage. Agents are identified by
strings so they serialize across processes: built-in names (`pass`, `random`,
`starter`) or paths to `.py` files with an `agent(obs)` at the top level.

Every episode is reproducible from (agent_a, agent_b, seed, seat_0, config).
"""

from __future__ import annotations

import time
from collections.abc import Sequence
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass(frozen=True, slots=True)
class EpisodeResult:
    agent_a: str
    agent_b: str
    seed: int
    seat_0: str  # "a" or "b"
    # rewards / statuses indexed by seat (0, 1), not by agent name.
    rewards: tuple[float, float]
    statuses: tuple[str, str]
    duration_seconds: float
    replay_path: str | None = None
    config: dict[str, Any] = field(default_factory=dict)

    @property
    def reward_a(self) -> float:
        return self.rewards[0] if self.seat_0 == "a" else self.rewards[1]

    @property
    def reward_b(self) -> float:
        return self.rewards[1] if self.seat_0 == "a" else self.rewards[0]

    @property
    def winner(self) -> str | None:
        """Return `"a"`, `"b"`, or `None` for a tie."""
        if self.reward_a > self.reward_b:
            return "a"
        if self.reward_b > self.reward_a:
            return "b"
        return None


def run_episode(
    agent_a: str,
    agent_b: str,
    seed: int,
    *,
    seat_0: str = "a",
    replay_dir: Path | None = None,
    config: dict[str, Any] | None = None,
) -> EpisodeResult:
    """Run one episode. `seat_0` picks which of a/b starts in player-0 seat."""
    if seat_0 not in ("a", "b"):
        raise ValueError(f"seat_0 must be 'a' or 'b', got {seat_0!r}")

    from kaggle_environments import make

    full_config: dict[str, Any] = {"episodeSteps": 720, "seed": seed}
    if config:
        full_config.update(config)

    p0, p1 = (agent_a, agent_b) if seat_0 == "a" else (agent_b, agent_a)

    start = time.perf_counter()
    env = make("kaggriculture", configuration=full_config)
    env.run([p0, p1])
    duration = time.perf_counter() - start

    final = env.steps[-1]
    rewards = (float(final[0].reward or 0.0), float(final[1].reward or 0.0))
    statuses = (str(final[0].status), str(final[1].status))

    replay_path: str | None = None
    if replay_dir is not None:
        replay_dir.mkdir(parents=True, exist_ok=True)
        replay_path = str(
            replay_dir / f"seed{seed}-a{seat_0}-{Path(agent_a).stem}-vs-{Path(agent_b).stem}.json"
        )
        import json

        with open(replay_path, "w", encoding="utf-8") as fh:
            json.dump(env.toJSON(), fh)

    return EpisodeResult(
        agent_a=agent_a,
        agent_b=agent_b,
        seed=seed,
        seat_0=seat_0,
        rewards=rewards,
        statuses=statuses,
        duration_seconds=duration,
        replay_path=replay_path,
        config=full_config,
    )


def _worker(args: tuple[str, str, int, str, Path | None, dict[str, Any] | None]) -> EpisodeResult:
    """Multiprocessing entry point (must be top-level and picklable)."""
    agent_a, agent_b, seed, seat_0, replay_dir, config = args
    return run_episode(
        agent_a,
        agent_b,
        seed,
        seat_0=seat_0,
        replay_dir=replay_dir,
        config=config,
    )


def run_pairing(
    agent_a: str,
    agent_b: str,
    seeds: Sequence[int],
    *,
    workers: int | None = None,
    swap_seats: bool = True,
    replay_dir: Path | None = None,
    config: dict[str, Any] | None = None,
) -> list[EpisodeResult]:
    """Run a full pairing across `seeds`, optionally with seat swaps."""
    tasks: list[tuple[str, str, int, str, Path | None, dict[str, Any] | None]] = []
    seats = ("a", "b") if swap_seats else ("a",)
    for seed in seeds:
        for seat_0 in seats:
            tasks.append((agent_a, agent_b, seed, seat_0, replay_dir, config))

    if workers == 1 or (workers is None and len(tasks) == 1):
        return [_worker(t) for t in tasks]

    results: list[EpisodeResult] = []
    with ProcessPoolExecutor(max_workers=workers) as ex:
        futures = [ex.submit(_worker, t) for t in tasks]
        for fut in as_completed(futures):
            results.append(fut.result())
    return results


def summarize(results: Sequence[EpisodeResult]) -> dict[str, Any]:
    """Compute headline stats for a list of episodes."""
    n = len(results)
    if n == 0:
        return {"n": 0}
    wins_a = sum(1 for r in results if r.winner == "a")
    wins_b = sum(1 for r in results if r.winner == "b")
    ties = sum(1 for r in results if r.winner is None)
    mean_gap = sum(r.reward_a - r.reward_b for r in results) / n
    mean_dur = sum(r.duration_seconds for r in results) / n
    return {
        "n": n,
        "wins_a": wins_a,
        "wins_b": wins_b,
        "ties": ties,
        "win_rate_a": wins_a / n,
        "win_rate_b": wins_b / n,
        "mean_coin_gap_a_minus_b": mean_gap,
        "mean_duration_seconds": mean_dur,
    }
