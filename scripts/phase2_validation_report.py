"""Evaluate the frozen second-cycle gate once both complete panels are available."""

import argparse
import json
from pathlib import Path

import numpy as np
from evidence_io import read_result
from phase2_compare import compare_manifests
from phase2_paired_report import NEW, OLD, OPPONENTS


def telemetry(rows):
    """Report episode-level distributions without inventing pooled action quantiles."""

    def distribution(values):
        return dict(
            zip(
                ("mean", "p50", "p95", "max"),
                (float(np.mean(values)), *np.quantile(values, [0.5, 0.95, 1]).tolist()),
                strict=True,
            )
        )

    return {
        "games": len(rows),
        "game_seconds": distribution([row["seconds"] for row in rows]),
        "per_game_action_p99_seconds": distribution([row["runtime_p99_seconds"] for row in rows]),
        "per_game_action_max_seconds": distribution([row["runtime_max_seconds"] for row in rows]),
        "stderr_turns": sum(row["stderr_turns"] for row in rows),
        "errors": sum(row["statuses"][row["seat"]] != "DONE" for row in rows),
        "losses_mean_per_game": {
            key: float(np.mean([row.get("losses", {}).get(key, 0) for row in rows]))
            for key in sorted({key for row in rows for key in row.get("losses", {})})
        },
        "actions_mean_per_game": {
            key: float(np.mean([row.get("realized_actions", {}).get(key, 0) for row in rows]))
            for key in sorted({key for row in rows for key in row.get("realized_actions", {})})
        },
        "fallback_measure": "Assignment fallback writes stderr; zero stderr establishes zero observed fallbacks. Nonzero stderr is not automatically a fallback count.",
        "daily_trajectory": [
            {
                "step": step,
                **{
                    key: float(
                        np.mean(
                            [
                                day[key]
                                for row in rows
                                for day in row["daily"]
                                if day["step"] == step
                            ]
                        )
                    )
                    for key in ("cash", "crops", "animals", "land", "shed", "carried")
                },
            }
            for step in sorted({day["step"] for row in rows for day in row["daily"]})
        ],
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--incumbent",
        type=Path,
        default=Path("reports/results/phase2-validation-incumbent.json.gz"),
    )
    parser.add_argument(
        "--challenger",
        type=Path,
        default=Path("reports/results/phase2-validation-challenger.json.gz"),
    )
    parser.add_argument(
        "--packaging", type=Path, default=Path("reports/results/phase2-challenger-packaging.json")
    )
    parser.add_argument(
        "--output", type=Path, default=Path("reports/results/phase2-validation-summary.json")
    )
    args = parser.parse_args()
    old, new = read_result(args.incumbent), read_result(args.challenger)
    anchor = compare_manifests(old, new, dict.fromkeys(OPPONENTS[:2], 0.5))
    challenge = compare_manifests(old, new, dict.fromkeys(OPPONENTS[2:], 0.5))
    assert anchor["seeds"] == list(range(2000, 2064))
    assert len(old["episodes"]) == len(new["episodes"]) == 512
    assert anchor["identities"]["incumbent"]["sha256"] == OLD
    assert anchor["identities"]["challenger"]["sha256"] == NEW
    packaging = json.loads(args.packaging.read_text())
    assert packaging["sha256"] == NEW
    measures = {"incumbent": telemetry(old["episodes"]), "challenger": telemetry(new["episodes"])}
    gates = {
        "anchor_delta_at_least_5pp": anchor["aggregate"]["score_delta"] >= 0.05,
        "anchor_delta_lower_95_bound_positive": anchor["aggregate"]["delta_ci95"][0] > 0,
        "evaluated_primary_anchor_floor_40pct": all(
            row["challenger_score"] >= 0.4 for row in anchor["opponents"].values()
        ),
        "challenge_delta_positive": challenge["aggregate"]["score_delta"] > 0,
        "challenge_score_at_least_50pct": challenge["aggregate"]["challenger_score"] >= 0.5,
        "candidate_errors_zero": measures["challenger"]["errors"] == 0,
        "packaging_passed": packaging["trajectory_actions_compared"] == 2876
        and packaging["fresh_processes"] == 2,
        "local_runtime_headroom": measures["challenger"]["per_game_action_max_seconds"]["max"]
        < 0.5,
    }
    report = {
        "purpose": "One frozen validation panel; no tuning on partial outcomes",
        "anchor": anchor,
        "challenge": challenge,
        "telemetry": measures,
        "gates": gates,
        "statistical_and_local_reliability_gates_pass": all(gates.values()),
        "holdout": "20000..20127 unopened; required before promotion if these gates pass",
        "hosted_evidence": "Unavailable: Kaggle authentication required",
        "coverage_limit": "The two primary anchors were rerun. Supplementary Tina crop-only results remain historical; no new crop-only validation claim is made.",
    }
    args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {"gates": gates, "anchor": anchor["aggregate"], "challenge": challenge["aggregate"]},
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
