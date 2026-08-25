"""Tests for the HTML replay viewer."""

from __future__ import annotations

from pathlib import Path

from kaggriculture.eval.view import _sanitize_name, main, render_episode


def test_sanitize_name_normalizes_paths_and_specials() -> None:
    assert _sanitize_name("pass") == "pass"
    assert _sanitize_name("path/to/agent.py") == "agent"
    assert _sanitize_name("weird name!") == "weird_name_"


def test_render_episode_returns_nonempty_html() -> None:
    html = render_episode("pass", "pass", seed=0, config={"episodeSteps": 24})
    assert isinstance(html, str)
    # The visualizer bundle is at least tens of KB even for a short episode.
    assert len(html) > 10_000
    assert "<html" in html.lower() or "<!doctype" in html.lower()


def test_cli_writes_html_and_does_not_open_when_flagged(tmp_path: Path) -> None:
    out = tmp_path / "replay.html"
    rc = main(
        [
            "pass",
            "pass",
            "--seed",
            "0",
            "--config",
            '{"episodeSteps": 24}',
            "--output",
            str(out),
            "--no-open",
        ]
    )
    assert rc == 0
    assert out.exists()
    assert out.stat().st_size > 10_000
