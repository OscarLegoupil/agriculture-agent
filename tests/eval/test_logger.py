"""Tests for the replay logger."""

from __future__ import annotations

from pathlib import Path

from kaggriculture.eval import (
    iter_replays,
    load_replay,
    new_run_id,
    read_manifest,
    run_pairing,
    write_manifest,
)


def test_new_run_id_is_unique() -> None:
    ids = {new_run_id() for _ in range(20)}
    assert len(ids) == 20


def test_manifest_round_trip(tmp_path: Path) -> None:
    root = tmp_path / new_run_id()
    results = run_pairing(
        "pass",
        "pass",
        seeds=[0, 1],
        workers=1,
        swap_seats=False,
        replay_dir=root,
        config={"episodeSteps": 48},
    )
    manifest_path = write_manifest(root, results)
    assert manifest_path.exists()

    rows = read_manifest(root)
    assert len(rows) == 2
    assert {r["seed"] for r in rows} == {0, 1}
    assert all(r["replay_path"] is not None for r in rows)

    # Round-trip: read every replay JSON and confirm it parses.
    pairs = list(iter_replays(root))
    assert len(pairs) == 2
    for meta, replay in pairs:
        assert isinstance(meta, dict)
        assert isinstance(replay, dict)
        assert "steps" in replay


def test_load_replay_reads_written_file(tmp_path: Path) -> None:
    root = tmp_path / new_run_id()
    results = run_pairing(
        "pass",
        "pass",
        seeds=[0],
        workers=1,
        swap_seats=False,
        replay_dir=root,
        config={"episodeSteps": 24},
    )
    (r,) = results
    assert r.replay_path is not None
    replay = load_replay(r.replay_path)
    assert "steps" in replay
    assert len(replay["steps"]) > 0
