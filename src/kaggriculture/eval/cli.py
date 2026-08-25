"""Command-line A/B comparison of two agents.

Runs a full pairing across a fixed seed set (default: swap seats to average
out seat 0 advantage), reports win rates with Wilson CIs, a two-sided sign
test p-value on the decisive matches, and the Bradley-Terry Elo delta.

Usage:
    uv run kagg-compare pass starter --n 50
    uv run kagg-compare pass starter --n 100 --replay-dir data/raw/replays
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path

from kaggriculture.eval import (
    EpisodeResult,
    bradley_terry_fit,
    bradley_terry_to_elo_scale,
    episodes_to_matches,
    new_run_id,
    run_pairing,
    write_manifest,
)
from kaggriculture.eval.stats import sign_test_two_sided, wilson_ci


@dataclass(frozen=True, slots=True)
class Summary:
    agent_a: str
    agent_b: str
    n_episodes: int
    duration_seconds: float
    wins_a: int
    wins_b: int
    ties: int
    win_rate_a: float
    win_rate_b: float
    ci95_a: tuple[float, float]
    ci95_b: tuple[float, float]
    sign_test_two_sided_p: float
    mean_coin_gap_a_minus_b: float
    bradley_terry_elo: dict[str, float] = field(default_factory=dict)
    elo_delta_a_minus_b: float = 0.0
    replay_dir: str | None = None


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    ap = argparse.ArgumentParser(
        prog="kagg-compare",
        description="Head-to-head A/B evaluation of two agents.",
    )
    ap.add_argument(
        "agent_a", help="Built-in name ('pass', 'random', 'starter') or path to a .py file"
    )
    ap.add_argument("agent_b", help="Built-in name or path to a .py file")
    ap.add_argument("-n", "--n", type=int, default=100, help="Episodes per seat (default 100)")
    ap.add_argument("--seed-start", type=int, default=0, help="First seed (default 0)")
    ap.add_argument(
        "--no-swap-seats", action="store_true", help="Skip the seat swap (biases results)"
    )
    ap.add_argument(
        "--workers", type=int, default=None, help="Process pool size (default: system default)"
    )
    ap.add_argument(
        "--replay-dir", type=Path, default=None, help="Save replays under <dir>/<run_id>/"
    )
    ap.add_argument("--config", type=str, default=None, help="JSON dict of extra env configuration")
    ap.add_argument(
        "--json", action="store_true", help="Emit a JSON result summary instead of text"
    )
    ap.add_argument(
        "--mlflow",
        action="store_true",
        help="Log this comparison to MLflow (requires tracking extra)",
    )
    ap.add_argument("--mlflow-experiment", default="kaggriculture", help="MLflow experiment name")
    ap.add_argument(
        "--mlflow-uri", default=None, help="MLflow tracking URI (default local mlruns/)"
    )
    return ap.parse_args(argv)


def _summary_dict(
    agent_a: str,
    agent_b: str,
    results: list[EpisodeResult],
    elapsed: float,
    replay_dir: Path | None,
) -> Summary:
    n = len(results)
    wins_a = sum(1 for r in results if r.winner == "a")
    wins_b = sum(1 for r in results if r.winner == "b")
    ties = sum(1 for r in results if r.winner is None)

    lo_a, hi_a = wilson_ci(wins_a, n)
    lo_b, hi_b = wilson_ci(wins_b, n)
    p_value = sign_test_two_sided(wins_a, wins_b)

    matches = episodes_to_matches(results)
    strengths = bradley_terry_fit(matches)
    elo = bradley_terry_to_elo_scale(strengths)

    return Summary(
        agent_a=agent_a,
        agent_b=agent_b,
        n_episodes=n,
        duration_seconds=elapsed,
        wins_a=wins_a,
        wins_b=wins_b,
        ties=ties,
        win_rate_a=wins_a / n if n else 0.0,
        win_rate_b=wins_b / n if n else 0.0,
        ci95_a=(lo_a, hi_a),
        ci95_b=(lo_b, hi_b),
        sign_test_two_sided_p=p_value,
        mean_coin_gap_a_minus_b=(sum(r.reward_a - r.reward_b for r in results) / n if n else 0.0),
        bradley_terry_elo=elo,
        elo_delta_a_minus_b=elo.get(agent_a, 0.0) - elo.get(agent_b, 0.0),
        replay_dir=str(replay_dir) if replay_dir else None,
    )


def _print_text(s: Summary) -> None:
    print(f"=== kagg-compare: {s.agent_a} vs {s.agent_b} ===")
    print(
        f"episodes: {s.n_episodes}  duration: {s.duration_seconds:.1f}s  "
        f"({s.duration_seconds / max(1, s.n_episodes):.2f}s/ep)"
    )
    print()
    print(
        f"{s.agent_a:<20}  W: {s.wins_a:>4}  L: {s.wins_b:>4}  T: {s.ties:>3}   "
        f"win_rate: {s.win_rate_a:.1%}   [95% CI: {s.ci95_a[0]:.1%}-{s.ci95_a[1]:.1%}]"
    )
    print(
        f"{s.agent_b:<20}  W: {s.wins_b:>4}  L: {s.wins_a:>4}  T: {s.ties:>3}   "
        f"win_rate: {s.win_rate_b:.1%}   [95% CI: {s.ci95_b[0]:.1%}-{s.ci95_b[1]:.1%}]"
    )
    print()
    print(f"sign test (two-sided): p = {s.sign_test_two_sided_p:.3g}")
    print(f"mean coin gap (a - b): {s.mean_coin_gap_a_minus_b:+.1f}")
    print()
    print("Bradley-Terry Elo (mean 1500):")
    for agent, r in sorted(s.bradley_terry_elo.items(), key=lambda kv: -kv[1]):
        print(f"  {agent:<20}  {r:.1f}")
    print(f"  delta (a - b): {s.elo_delta_a_minus_b:+.1f}")
    if s.replay_dir:
        print()
        print(f"replays: {s.replay_dir}")


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    config = json.loads(args.config) if args.config else None
    seeds = list(range(args.seed_start, args.seed_start + args.n))

    replay_dir: Path | None = None
    if args.replay_dir is not None:
        run_id = new_run_id()
        replay_dir = args.replay_dir / run_id

    start = time.perf_counter()
    results = run_pairing(
        args.agent_a,
        args.agent_b,
        seeds,
        workers=args.workers,
        swap_seats=not args.no_swap_seats,
        replay_dir=replay_dir,
        config=config,
    )
    elapsed = time.perf_counter() - start

    if replay_dir is not None:
        write_manifest(replay_dir, results)

    summary = _summary_dict(args.agent_a, args.agent_b, results, elapsed, replay_dir)

    if args.mlflow:
        from kaggriculture.eval.tracking import log_to_mlflow

        run_id = log_to_mlflow(
            summary,
            results,
            experiment_name=args.mlflow_experiment,
            tracking_uri=args.mlflow_uri,
        )
        print(f"mlflow run_id: {run_id}", file=sys.stderr)

    if args.json:
        json.dump(asdict(summary), sys.stdout, indent=2)
        print()
    else:
        _print_text(summary)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
