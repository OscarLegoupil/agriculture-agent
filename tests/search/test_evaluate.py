"""Tests for the search config evaluator (agent-file generation)."""

from __future__ import annotations

from pathlib import Path

from kaggriculture.search.evaluate import build_agent_file


def test_build_agent_file_embeds_yaml_and_kwargs(tmp_path: Path) -> None:
    yaml_text = "name: test\ncrops: []\n"
    out = tmp_path / "agent.py"
    build_agent_file(
        yaml_text=yaml_text,
        micro_kwargs={"tail_start_day": 22, "salvage_ratio": 0.85},
        out_path=out,
    )
    text = out.read_text(encoding="utf-8")
    assert "route_from_dict" in text
    assert "tail_start_day=22" in text
    assert "salvage_ratio=0.85" in text
    # The YAML content must be embedded as a string literal.
    assert "name: test" in text
