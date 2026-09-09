"""Paired-seed uncertainty and per-opponent benchmark summaries."""

import argparse
import json
from collections import defaultdict
from pathlib import Path

import numpy as np


def match_score(row):
    if row["statuses"][row["seat"]] != "DONE":
        return 0.0
    if row["statuses"][1 - row["seat"]] != "DONE":
        return 1.0
    return float(row["cash"] > row["opponent_cash"]) + 0.5 * (row["cash"] == row["opponent_cash"])


def summarize(rows, primary=None):
    grouped = defaultdict(list)
    for row in rows:
        grouped[row["opponent"]].append(row)
    if primary is None:
        declared = ["data/raw/reference-lonespear/main.py", "data/raw/reference-gzm/main.py"]
        primary = declared if all(opponent in grouped for opponent in declared) else []
    report = {"opponents": {}}
    for opponent, games in grouped.items():
        paired = defaultdict(list)
        for row in games:
            paired[row["seed"]].append(match_score(row))
        values = np.array([np.mean(scores) for scores in paired.values()])
        samples = (
            np.random.default_rng(20260909).choice(values, size=(10000, len(values))).mean(axis=1)
        )
        gaps = [float(row["cash"] or 0) - float(row["opponent_cash"] or 0) for row in games]
        report["opponents"][opponent] = {
            "games": len(games),
            "seeds": len(paired),
            "wins": sum(match_score(row) == 1 for row in games),
            "draws": sum(match_score(row) == 0.5 for row in games),
            "score": float(np.mean(values)),
            "ci95": np.quantile(samples, [0.025, 0.975]).tolist(),
            "mean_cash": float(np.mean([row["cash"] or 0 for row in games])),
            "mean_opponent_cash": float(np.mean([row["opponent_cash"] or 0 for row in games])),
            "mean_gap": float(np.mean(gaps)),
            "p10_gap": float(np.quantile(gaps, 0.1)),
            "errors": sum(row["statuses"][row["seat"]] != "DONE" for row in games),
            "stderr_turns": sum(row.get("stderr_turns", 0) for row in games),
            "max_action_seconds": max(row.get("runtime_max_seconds", 0) for row in games),
            "max_p99_action_seconds": max(row.get("runtime_p99_seconds", 0) for row in games),
        }
    if primary:
        seeds = sorted(set.intersection(*(set(r["seed"] for r in grouped[o]) for o in primary)))
        values = []
        for seed in seeds:
            blocks = [[r for r in grouped[o] if r["seed"] == seed] for o in primary]
            if any(sorted(r["seat"] for r in block) != [0, 1] for block in blocks):
                raise ValueError("Primary summary requires both seats once per opponent and seed")
            values.append(np.mean([np.mean([match_score(r) for r in block]) for block in blocks]))
        bootstrap = (
            np.random.default_rng(20260909).choice(values, size=(10000, len(values))).mean(axis=1)
        )
        ci = np.quantile(bootstrap, [0.025, 0.975]).tolist()
        report["primary"] = {
            "weights": {o: 1 / len(primary) for o in primary},
            "seeds": len(seeds),
            "score": float(np.mean(values)),
            "ci95": ci,
            "gate_passed": ci[0] > 0.5
            and all(v["errors"] == 0 and v["score"] >= 0.4 for v in report["opponents"].values()),
        }
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    report = summarize(json.loads(args.input.read_text())["episodes"])
    text = json.dumps(report, indent=2)
    if args.output:
        args.output.write_text(text + "\n", encoding="utf-8")
    print(text)
