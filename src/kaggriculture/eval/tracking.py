"""MLflow tracking for A/B evaluations.

One MLflow run per (agent_a, agent_b, opponent-pool) comparison. Params
capture what was run; metrics capture the outcome; artifacts (manifest and
per-episode metrics parquet) let downstream analysis reload results.

MLflow is imported lazily so the rest of the eval harness has no runtime
dependency on it. Install with `uv sync --extra tracking`.
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from kaggriculture.eval.cli import Summary
    from kaggriculture.eval.runner import EpisodeResult


def log_to_mlflow(
    summary: Summary,
    results: list[EpisodeResult],
    *,
    experiment_name: str = "kaggriculture",
    tracking_uri: str | None = None,
    tags: dict[str, str] | None = None,
) -> str:
    """Log a comparison run to MLflow. Return the run_id."""
    import mlflow  # local import: mlflow is an optional extra

    if tracking_uri is not None:
        mlflow.set_tracking_uri(tracking_uri)
    mlflow.set_experiment(experiment_name)

    with mlflow.start_run(tags=tags or {}) as run:
        mlflow.log_params(
            {
                "agent_a": summary.agent_a,
                "agent_b": summary.agent_b,
                "n_episodes": summary.n_episodes,
                "swap_seats": len({r.seat_0 for r in results}) > 1,
                "seeds_start": min(r.seed for r in results) if results else None,
                "seeds_end": max(r.seed for r in results) if results else None,
                "replay_dir": summary.replay_dir,
            }
        )
        mlflow.log_metrics(
            {
                "win_rate_a": summary.win_rate_a,
                "win_rate_b": summary.win_rate_b,
                "wins_a": float(summary.wins_a),
                "wins_b": float(summary.wins_b),
                "ties": float(summary.ties),
                "ci95_a_lo": summary.ci95_a[0],
                "ci95_a_hi": summary.ci95_a[1],
                "ci95_b_lo": summary.ci95_b[0],
                "ci95_b_hi": summary.ci95_b[1],
                "sign_test_p": summary.sign_test_two_sided_p,
                "mean_coin_gap_a_minus_b": summary.mean_coin_gap_a_minus_b,
                "elo_a": summary.bradley_terry_elo.get(summary.agent_a, 0.0),
                "elo_b": summary.bradley_terry_elo.get(summary.agent_b, 0.0),
                "elo_delta_a_minus_b": summary.elo_delta_a_minus_b,
                "duration_seconds": summary.duration_seconds,
            }
        )

        with tempfile.TemporaryDirectory() as td:
            summary_path = Path(td) / "summary.json"
            summary_path.write_text(
                json.dumps(
                    {
                        "agent_a": summary.agent_a,
                        "agent_b": summary.agent_b,
                        "wins_a": summary.wins_a,
                        "wins_b": summary.wins_b,
                        "ties": summary.ties,
                        "bradley_terry_elo": summary.bradley_terry_elo,
                    },
                    indent=2,
                ),
            )
            mlflow.log_artifact(str(summary_path))

        return str(run.info.run_id)
