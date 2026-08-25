"""Replay storage: manifest, load, iterate.

Replays are large per-episode JSONs (`env.toJSON()`). We store them under
`data/raw/replays/<run_id>/` and maintain a JSON-lines manifest so downstream
analysis code can iterate over a run without parsing every replay.
"""

from __future__ import annotations

import json
import uuid
from collections.abc import Iterable, Iterator
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from kaggriculture.eval.runner import EpisodeResult


def new_run_id() -> str:
    """Human-readable timestamp + short random suffix."""
    ts = datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
    suffix = uuid.uuid4().hex[:6]
    return f"{ts}-{suffix}"


def write_manifest(root: Path, results: Iterable[EpisodeResult]) -> Path:
    """Write a `manifest.jsonl` summarizing episode metadata + replay paths."""
    root.mkdir(parents=True, exist_ok=True)
    path = root / "manifest.jsonl"
    with open(path, "w", encoding="utf-8") as fh:
        for r in results:
            row = asdict(r)
            fh.write(json.dumps(row, default=str) + "\n")
    return path


def read_manifest(root: Path) -> list[dict[str, Any]]:
    path = root / "manifest.jsonl"
    if not path.exists():
        return []
    rows = []
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def load_replay(path: str | Path) -> dict[str, Any]:
    with open(path, encoding="utf-8") as fh:
        result: dict[str, Any] = json.load(fh)
        return result


def iter_replays(root: Path) -> Iterator[tuple[dict[str, Any], dict[str, Any]]]:
    """Yield `(manifest_row, replay_json)` for every episode in a run."""
    for row in read_manifest(root):
        replay_path = row.get("replay_path")
        if replay_path is None:
            continue
        yield row, load_replay(replay_path)
