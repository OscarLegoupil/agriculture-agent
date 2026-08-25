"""Tests for the A/B compare CLI and its statistical helpers."""

from __future__ import annotations

import math
import subprocess
import sys

from kaggriculture.eval.cli import _summary_dict, main
from kaggriculture.eval.runner import EpisodeResult
from kaggriculture.eval.stats import sign_test_two_sided, wilson_ci


def test_wilson_ci_symmetric_case() -> None:
    lo, hi = wilson_ci(50, 100)
    assert 0.0 <= lo < 0.5 < hi <= 1.0


def test_wilson_ci_zero_wins() -> None:
    lo, hi = wilson_ci(0, 20)
    assert lo == 0.0
    assert 0.0 < hi < 0.5


def test_sign_test_extreme() -> None:
    # 100 wins, 0 losses: p-value should be < 1e-20.
    p = sign_test_two_sided(100, 0)
    assert p < 1e-20


def test_sign_test_even() -> None:
    p = sign_test_two_sided(50, 50)
    assert 0.9 < p <= 1.0


def test_summary_dict_shape() -> None:
    results = [
        EpisodeResult("a", "b", 0, "a", (100.0, 50.0), ("DONE", "DONE"), 0.1),
        EpisodeResult("a", "b", 0, "b", (60.0, 40.0), ("DONE", "DONE"), 0.1),
        EpisodeResult("a", "b", 1, "a", (30.0, 90.0), ("DONE", "DONE"), 0.1),
        EpisodeResult("a", "b", 1, "b", (10.0, 30.0), ("DONE", "DONE"), 0.1),
    ]
    s = _summary_dict("a", "b", results, elapsed=1.0, replay_dir=None)
    assert s.n_episodes == 4
    assert set(s.bradley_terry_elo) == {"a", "b"}
    assert math.isfinite(s.elo_delta_a_minus_b)


def test_cli_smoke_json(capsys: object) -> None:
    rc = main(
        [
            "pass",
            "pass",
            "--n",
            "2",
            "--config",
            '{"episodeSteps": 48}',
            "--json",
            "--workers",
            "1",
        ]
    )
    assert rc == 0
    captured = capsys.readouterr()  # type: ignore[attr-defined]
    import json as _json

    payload = _json.loads(captured.out)
    assert payload["agent_a"] == "pass"
    assert payload["agent_b"] == "pass"
    assert payload["n_episodes"] == 4
    # Two identical pass agents always tie.
    assert payload["ties"] == 4


def test_cli_console_entry_point_installed() -> None:
    # `kagg-compare --help` must be resolvable in the current uv env.
    result = subprocess.run(
        [sys.executable, "-m", "kaggriculture.eval.cli", "--help"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0
    assert "kagg-compare" in result.stdout
