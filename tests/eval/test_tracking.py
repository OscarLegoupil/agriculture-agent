"""Test MLflow tracking (skipped if mlflow is not installed)."""
# ruff: noqa: E402

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

pytest.importorskip("mlflow")

from kaggriculture.eval.cli import _summary_dict
from kaggriculture.eval.runner import EpisodeResult
from kaggriculture.eval.tracking import log_to_mlflow


def test_log_to_mlflow_writes_run(tmp_path: Path) -> None:
    results = [
        EpisodeResult("agent_x", "agent_y", 0, "a", (100.0, 50.0), ("DONE", "DONE"), 0.1),
        EpisodeResult("agent_x", "agent_y", 0, "b", (60.0, 40.0), ("DONE", "DONE"), 0.1),
        EpisodeResult("agent_x", "agent_y", 1, "a", (30.0, 90.0), ("DONE", "DONE"), 0.1),
        EpisodeResult("agent_x", "agent_y", 1, "b", (10.0, 30.0), ("DONE", "DONE"), 0.1),
    ]
    summary = _summary_dict("agent_x", "agent_y", results, elapsed=1.0, replay_dir=None)

    tracking_uri = f"sqlite:///{tmp_path.as_posix()}/mlflow.db"
    run_id = log_to_mlflow(
        summary,
        results,
        experiment_name="kagg-test",
        tracking_uri=tracking_uri,
    )
    assert isinstance(run_id, str)
    assert len(run_id) > 0

    shutil.rmtree(tmp_path, ignore_errors=True)
