"""Tests for per-episode metrics extraction."""

from __future__ import annotations

from pathlib import Path

from kaggriculture.eval import (
    collect_metrics,
    extract_metrics,
    flatten_row,
    load_replay,
    new_run_id,
    run_pairing,
    write_manifest,
)


def test_extract_metrics_over_pass_vs_starter(tmp_path: Path) -> None:
    root = tmp_path / new_run_id()
    results = run_pairing(
        "pass",
        "starter",
        seeds=[0],
        workers=1,
        swap_seats=False,
        replay_dir=root,
        config={"episodeSteps": 240},
    )
    (r,) = results
    assert r.replay_path is not None
    replay = load_replay(r.replay_path)
    m = extract_metrics(replay)

    assert m["n_steps"] > 0
    assert len(m["final_coins"]) == 2
    # Pass agent should end at starting money.
    assert m["final_coins"][0] == 3000.0
    # Starter buys and plants carrots; final money differs from 3000.
    assert m["final_coins"][1] != 3000.0
    assert m["winner"] in ("0", "1", "tie")
    assert isinstance(m["farmer_ops"][0], dict)
    assert m["farmer_ops"][0].get("PASS", 0) > 0
    # Starter issues BUY_SEED CARROT and SELL CARROT market orders.
    assert m["market_ops"][1].get("BUY_SEED", 0) > 0
    assert m["total_hires"] == [0, 0]
    assert m["final_quadrants"] == [1, 1]


def test_flatten_row_produces_scalar_columns(tmp_path: Path) -> None:
    root = tmp_path / new_run_id()
    results = run_pairing(
        "pass",
        "starter",
        seeds=[0],
        workers=1,
        swap_seats=False,
        replay_dir=root,
        config={"episodeSteps": 96},
    )
    (r,) = results
    assert r.replay_path is not None
    replay = load_replay(r.replay_path)
    row = flatten_row(extract_metrics(replay))

    assert "seed" in row
    assert "final_coins_0" in row
    assert "final_coins_1" in row
    assert "coin_gap_0_minus_1" in row
    # Every value must be a scalar (not a list or dict).
    for k, v in row.items():
        assert not isinstance(v, list | dict), (k, v)


def test_collect_metrics_walks_manifest(tmp_path: Path) -> None:
    root = tmp_path / new_run_id()
    results = run_pairing(
        "pass",
        "starter",
        seeds=[0, 1],
        workers=1,
        swap_seats=True,
        replay_dir=root,
        config={"episodeSteps": 48},
    )
    write_manifest(root, results)

    rows = collect_metrics(root)
    assert len(rows) == 4  # 2 seeds x 2 seat assignments
    assert all("_seat_0" in r for r in rows)
    assert {r["_seat_0"] for r in rows} == {"a", "b"}
