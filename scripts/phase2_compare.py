"""Matched policy comparison with complete-seed bootstrap uncertainty."""

import argparse
import gzip
import hashlib
import json
import math
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


def cash_gap(row):
    """Keep absent/non-finite rewards out of cash statistics, never out of scores."""
    own, rival = row.get("cash"), row.get("opponent_cash")
    if own is None or rival is None or not (math.isfinite(own) and math.isfinite(rival)):
        return None
    return float(own - rival)


def cash_summary(gaps):
    values = [value for value in gaps if value is not None]
    return {
        "n": len(values),
        "missing": len(gaps) - len(values),
        "mean": float(np.mean(values)) if values else None,
        "median": float(np.median(values)) if values else None,
        "p10": float(np.quantile(values, 0.1)) if values else None,
    }


def matched_panel(incumbent, challenger):
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
    for key in old:
        if old[key]["configuration"] != new[key]["configuration"]:
            raise ValueError(f"Configuration differs: {key}")
        if old[key].get("resolved_seed") != new[key].get("resolved_seed"):
            raise ValueError(f"Resolved seed differs: {key}")
    return old, new, opponents, seeds


def compare(incumbent, challenger, weights):
    old, new, opponents, seeds = matched_panel(incumbent, challenger)
    if (
        not weights
        or set(weights) - set(opponents)
        or any(v < 0 for v in weights.values())
        or not np.isclose(sum(weights.values()), 1)
    ):
        raise ValueError("Weights must be nonnegative and sum to one over present opponents")
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
        old_gaps = [cash_gap(old[opponent, seed, seat]) for seed in seeds for seat in (0, 1)]
        new_gaps = [cash_gap(new[opponent, seed, seat]) for seed in seeds for seat in (0, 1)]
        gap_changes = [
            after - before
            for before, after in zip(old_gaps, new_gaps, strict=True)
            if before is not None and after is not None
        ]
        old_games = [old[opponent, seed, seat] for seed in seeds for seat in (0, 1)]
        games = [new[opponent, seed, seat] for seed in seeds for seat in (0, 1)]
        report["opponents"][opponent] = {
            "games": len(games),
            "incumbent_score": float(paired[:, 0].mean()),
            "challenger_score": float(paired[:, 1].mean()),
            "score_delta": float(delta.mean()),
            "delta_ci95": np.quantile(delta[resamples].mean(axis=1), [0.025, 0.975]).tolist(),
            "incumbent_cash_gap": cash_summary(old_gaps),
            "challenger_cash_gap": cash_summary(new_gaps),
            "mean_paired_gap_change": float(np.mean(gap_changes)) if gap_changes else None,
            "paired_gap_n": len(gap_changes),
            "paired_gap_missing": len(games) - len(gap_changes),
            "candidate_errors": sum(r["statuses"][r["seat"]] != "DONE" for r in games),
            "opponent_errors": sum(r["statuses"][1 - r["seat"]] != "DONE" for r in games),
            "incumbent_errors": sum(r["statuses"][r["seat"]] != "DONE" for r in old_games),
            "incumbent_opponent_errors": sum(
                r["statuses"][1 - r["seat"]] != "DONE" for r in old_games
            ),
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


def candidate_identity(manifest):
    """Verify recorded source identity against the exact frozen and archived bytes."""
    source = manifest["arguments"]["candidate"]
    digest = manifest["hashes"][source]
    frozen_name = manifest["executed_candidate"]
    snapshot_name = manifest["candidate_snapshot"]
    frozen = Path(frozen_name.replace("\\", "/"))
    snapshot = Path(snapshot_name.replace("\\", "/"))
    if not frozen.is_file() or not snapshot.is_file():
        raise ValueError("Candidate verification requires frozen executable and source snapshot")
    frozen_bytes = frozen.read_bytes()
    archived_bytes = gzip.decompress(snapshot.read_bytes())
    if any(
        hashlib.sha256(content).hexdigest() != digest for content in (frozen_bytes, archived_bytes)
    ):
        raise ValueError("Candidate source, frozen executable, and snapshot hashes disagree")
    if any(
        row["candidate"].replace("\\", "/") != frozen_name.replace("\\", "/")
        for row in manifest["episodes"]
    ):
        raise ValueError("Episode candidate identity differs from frozen executable")
    return {
        "sha256": digest,
        "source": source,
        "executed_candidate": frozen_name,
        "snapshot": snapshot_name,
        "revision": manifest["revision"],
    }


def compare_manifests(old, new, weights):
    """Validate complete experiments before selecting the requested opponent pool."""
    if old.get("complete") is not True or new.get("complete") is not True:
        raise ValueError("Selection requires two completed, integrity-checked benchmarks")
    _, _, all_opponents, seeds = matched_panel(old["episodes"], new["episodes"])
    for opponent in all_opponents:
        if old["hashes"][opponent] != new["hashes"][opponent]:
            raise ValueError(f"Opponent executable changed: {opponent}")
    provenance_keys = ("environment_version", "interpreter_sha256", "lock_sha256", "dependencies")
    for key in provenance_keys:
        if old[key] != new[key]:
            raise ValueError(f"Provenance mismatch: {key}")
    identities = {"incumbent": candidate_identity(old), "challenger": candidate_identity(new)}
    if set(weights) - set(all_opponents):
        raise ValueError("Requested pool contains an absent opponent")
    report = compare(
        [row for row in old["episodes"] if row["opponent"] in weights],
        [row for row in new["episodes"] if row["opponent"] in weights],
        weights,
    )
    report["identities"] = identities
    report["provenance"] = {
        **{key: old[key] for key in provenance_keys},
        "all_opponent_hashes": {opponent: old["hashes"][opponent] for opponent in all_opponents},
        "scenario_configuration_sha256": hashlib.sha256(
            json.dumps(
                sorted(
                    (row["opponent"], row["seed"], row["seat"], row["configuration"])
                    for row in old["episodes"]
                ),
                sort_keys=True,
                separators=(",", ":"),
            ).encode()
        ).hexdigest(),
        "validated_full_panel": {
            "opponents": all_opponents,
            "seeds": seeds,
            "games_per_policy": len(old["episodes"]),
        },
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
    opponents = (
        ["data/raw/reference-lonespear/main.py", "data/raw/reference-gzm/main.py"]
        if args.pool == "anchor"
        else ["data/raw/reference-seyam/main.py", "data/raw/reference-cok/main.py"]
    )
    report = compare_manifests(old, new, dict.fromkeys(opponents, 0.5))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report["aggregate"], indent=2))
