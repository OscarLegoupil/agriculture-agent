"""Matched policy comparison with complete-seed bootstrap uncertainty."""

import argparse
import json
from pathlib import Path

import numpy as np

try:
    from .evidence_io import read_result
    from .summarize_benchmark import match_score
except ImportError:
    from evidence_io import read_result
    from summarize_benchmark import match_score


def indexed(rows):
    result = {}
    for row in rows:
        key = row["opponent"], row["seed"], row["seat"]
        if key in result:
            raise ValueError(f"Duplicate scenario: {key}")
        result[key] = row
    return result


def compare(incumbent, challenger, weights):
    old, new = indexed(incumbent), indexed(challenger)
    if old.keys() != new.keys():
        raise ValueError("Candidate and incumbent scenario sets differ")
    if not old:
        raise ValueError("Empty comparison")
    opponents = sorted({key[0] for key in old})
    seeds = sorted({key[1] for key in old})
    expected = {(o, s, seat) for o in opponents for s in seeds for seat in (0, 1)}
    if set(old) != expected:
        raise ValueError("Incomplete seed/seat/opponent panel")
    if (
        not weights
        or set(weights) - set(opponents)
        or any(v < 0 for v in weights.values())
        or not np.isclose(sum(weights.values()), 1)
    ):
        raise ValueError("Weights must be nonnegative and sum to one over present opponents")
    for key in old:
        if old[key]["configuration"] != new[key]["configuration"]:
            raise ValueError(f"Configuration differs: {key}")
        if old[key].get("resolved_seed") != new[key].get("resolved_seed"):
            raise ValueError(f"Resolved seed differs: {key}")
    rng = np.random.default_rng(20260910)
    resamples = rng.integers(len(seeds), size=(10000, len(seeds)))
    report = {"seeds": seeds, "weights": weights, "opponents": {}}
    scores = []
    for opponent in opponents:
        paired = np.array(
            [
                [
                    np.mean([match_score(rows[opponent, seed, seat]) for seat in (0, 1)])
                    for rows in (old, new)
                ]
                for seed in seeds
            ]
        )
        delta = paired[:, 1] - paired[:, 0]
        old_gaps = [
            old[opponent, seed, seat]["cash"] - old[opponent, seed, seat]["opponent_cash"]
            for seed in seeds
            for seat in (0, 1)
        ]
        new_gaps = [
            new[opponent, seed, seat]["cash"] - new[opponent, seed, seat]["opponent_cash"]
            for seed in seeds
            for seat in (0, 1)
        ]
        games = [new[opponent, seed, seat] for seed in seeds for seat in (0, 1)]
        report["opponents"][opponent] = {
            "games": len(games),
            "incumbent_score": float(paired[:, 0].mean()),
            "challenger_score": float(paired[:, 1].mean()),
            "score_delta": float(delta.mean()),
            "delta_ci95": np.quantile(delta[resamples].mean(axis=1), [0.025, 0.975]).tolist(),
            "incumbent_cash_gap": dict(
                zip(
                    ("mean", "median", "p10"),
                    (
                        float(np.mean(old_gaps)),
                        float(np.median(old_gaps)),
                        float(np.quantile(old_gaps, 0.1)),
                    ),
                    strict=True,
                )
            ),
            "challenger_cash_gap": dict(
                zip(
                    ("mean", "median", "p10"),
                    (
                        float(np.mean(new_gaps)),
                        float(np.median(new_gaps)),
                        float(np.quantile(new_gaps, 0.1)),
                    ),
                    strict=True,
                )
            ),
            "mean_paired_gap_change": float(np.mean(np.array(new_gaps) - old_gaps)),
            "candidate_errors": sum(r["statuses"][r["seat"]] != "DONE" for r in games),
            "stderr_turns": sum(r.get("stderr_turns", 0) for r in games),
            "max_action_seconds": max(r.get("runtime_max_seconds", 0) for r in games),
            "failed_work": sum(
                v
                for r in games
                for k, v in r.get("realized_actions", {}).items()
                if k.startswith("failed:")
            ),
        }
        scores.append(paired * weights.get(opponent, 0))
    aggregate = sum(scores)
    delta = aggregate[:, 1] - aggregate[:, 0]
    report["aggregate"] = {
        "incumbent_score": float(aggregate[:, 0].mean()),
        "challenger_score": float(aggregate[:, 1].mean()),
        "score_delta": float(delta.mean()),
        "delta_ci95": np.quantile(delta[resamples].mean(axis=1), [0.025, 0.975]).tolist(),
        "challenger_ci95": np.quantile(
            aggregate[:, 1][resamples].mean(axis=1), [0.025, 0.975]
        ).tolist(),
    }
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("incumbent", type=Path)
    parser.add_argument("challenger", type=Path)
    parser.add_argument("--pool", choices=("anchor", "challenge"), required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    old, new = read_result(args.incumbent), read_result(args.challenger)
    if not old.get("complete") or not new.get("complete"):
        raise ValueError("Selection requires two completed, integrity-checked benchmarks")
    opponents = (
        ["data/raw/reference-lonespear/main.py", "data/raw/reference-gzm/main.py"]
        if args.pool == "anchor"
        else ["data/raw/reference-seyam/main.py", "data/raw/reference-cok/main.py"]
    )
    for opponent in opponents:
        if old["hashes"][opponent] != new["hashes"][opponent]:
            raise ValueError(f"Opponent executable changed: {opponent}")
    for key in ("environment_version", "interpreter_sha256", "lock_sha256"):
        if old[key] != new[key]:
            raise ValueError(f"Provenance mismatch: {key}")
    report = compare(old["episodes"], new["episodes"], dict.fromkeys(opponents, 0.5))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report["aggregate"], indent=2))
