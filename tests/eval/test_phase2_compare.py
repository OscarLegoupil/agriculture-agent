"""Matched inference must reject missing scenarios and retain paired dependence."""

import gzip
import hashlib
import json
from copy import deepcopy

import pytest
from scripts.phase2_compare import compare, compare_manifests


def panel():
    return [
        {
            "opponent": opponent,
            "seed": seed,
            "seat": seat,
            "cash": 10,
            "opponent_cash": 10,
            "statuses": ["DONE", "DONE"],
            "configuration": {"seed": seed},
            "resolved_seed": seed,
        }
        for opponent in ("a", "b")
        for seed in (1, 2)
        for seat in (0, 1)
    ]


def test_matched_bootstrap_retains_candidate_and_seed_dependence():
    old, new = panel(), panel()
    for row in new:
        row["cash"] = 20 if row["seed"] == 1 else 0
    report = compare(old, new, {"a": 0.5, "b": 0.5})
    assert report["aggregate"]["score_delta"] == 0
    assert report["aggregate"]["delta_ci95"] == [-0.5, 0.5]
    assert compare(old, old, {"a": 0.5, "b": 0.5})["aggregate"]["delta_ci95"] == [0, 0]


def test_comparison_rejects_different_or_incomplete_scenarios():
    old = panel()
    with pytest.raises(ValueError, match="scenario sets differ"):
        compare(old, old[:-1], {"a": 0.5, "b": 0.5})
    with pytest.raises(ValueError, match="Incomplete"):
        compare(old[:-1], old[:-1], {"a": 0.5, "b": 0.5})
    with pytest.raises(ValueError, match="Duplicate"):
        compare(old + old[:1], old + old[:1], {"a": 0.5, "b": 0.5})
    changed = deepcopy(old)
    changed[0]["configuration"]["seed"] = 4
    with pytest.raises(ValueError, match="Configuration differs"):
        compare(old, changed, {"a": 0.5, "b": 0.5})


def test_errors_keep_score_denominator_and_cash_uses_complete_pairs():
    old, new = panel(), panel()
    # Both missing observations are in different scenarios. Dropping them
    # independently and subtracting the shortened arrays would mispair cash.
    old[0].update(cash=None, statuses=["ERROR", "DONE"])
    new[1].update(cash=None, statuses=["DONE", "TIMEOUT"])
    new[2].update(cash=25)
    # Opponent error in seat 1's game: the first status is the opponent's.
    new[3].update(opponent_cash=None, statuses=["ERROR", "DONE"])
    report = compare(old, new, {"a": 0.5, "b": 0.5})
    result = report["opponents"]["a"]
    assert result["games"] == 4
    assert result["incumbent_score"] == 0.375
    assert result["challenger_score"] == 0.625
    assert result["candidate_errors"] == 1
    assert result["opponent_errors"] == 1
    assert result["incumbent_errors"] == 1
    assert result["incumbent_opponent_errors"] == 0
    assert result["incumbent_cash_gap"]["n"] == 3
    assert result["challenger_cash_gap"]["n"] == 2
    assert result["challenger_cash_gap"]["missing"] == 2
    assert result["challenger_cash_gap"]["mean"] == 7.5
    assert result["paired_gap_n"] == 1
    assert result["paired_gap_missing"] == 3
    assert result["mean_paired_gap_change"] == 15
    json.dumps(report, allow_nan=False)


def test_all_errors_produce_null_cash_summaries_and_zero_scores():
    rows = panel()
    for row in rows:
        row.update(cash=None, opponent_cash=float("nan"), statuses=["ERROR", "ERROR"])
    report = compare(rows, rows, {"a": 0.5, "b": 0.5})
    assert report["aggregate"]["challenger_score"] == 0
    result = report["opponents"]["a"]
    assert result["candidate_errors"] == result["opponent_errors"] == 4
    assert result["challenger_cash_gap"] == {
        "n": 0,
        "missing": 4,
        "mean": None,
        "median": None,
        "p10": None,
    }
    assert result["mean_paired_gap_change"] is None
    assert result["paired_gap_n"] == 0
    json.dumps(report, allow_nan=False)


def manifest(tmp_path, name):
    directory = tmp_path / name
    directory.mkdir()
    content = f"# frozen {name}\n".encode()
    executable = directory / "main.py"
    executable.write_bytes(content)
    snapshot = directory / "main.py.gz"
    snapshot.write_bytes(gzip.compress(content, mtime=0))
    rows = panel()
    for row in rows:
        row["candidate"] = str(executable)
    return {
        "complete": True,
        "arguments": {"candidate": f"source-{name}.py"},
        "hashes": {
            f"source-{name}.py": hashlib.sha256(content).hexdigest(),
            "a": "opponent-a-hash",
            "b": "opponent-b-hash",
        },
        "executed_candidate": str(executable),
        "candidate_snapshot": str(snapshot),
        "revision": name,
        "environment_version": "1.32.7",
        "interpreter_sha256": "interpreter-hash",
        "lock_sha256": "lock-hash",
        "dependencies": {"numpy": "same-version"},
        "episodes": rows,
    }


def test_manifest_pool_selection_preserves_full_panel_integrity(tmp_path):
    old, new = manifest(tmp_path, "old"), manifest(tmp_path, "new")
    result = compare_manifests(old, new, {"a": 1.0})
    assert set(result["opponents"]) == {"a"}
    assert result["identities"]["challenger"]["sha256"] == new["hashes"]["source-new.py"]
    assert result["provenance"]["validated_full_panel"]["games_per_policy"] == 8
    # Unselected opponents must still match: selection cannot conceal changes.
    changed = deepcopy(new)
    changed["hashes"]["b"] = "changed"
    with pytest.raises(ValueError, match="Opponent executable changed"):
        compare_manifests(old, changed, {"a": 1.0})
    changed = deepcopy(new)
    changed["episodes"][-1]["configuration"]["seed"] = 99
    with pytest.raises(ValueError, match="Configuration differs"):
        compare_manifests(old, changed, {"a": 1.0})
    changed = deepcopy(new)
    changed["complete"] = False
    with pytest.raises(ValueError, match="completed"):
        compare_manifests(old, changed, {"a": 1.0})
    changed = deepcopy(new)
    changed["dependencies"]["numpy"] = "changed-version"
    with pytest.raises(ValueError, match="Provenance mismatch"):
        compare_manifests(old, changed, {"a": 1.0})


def test_manifest_rejects_candidate_identity_or_snapshot_mismatch(tmp_path):
    old, new = manifest(tmp_path, "old"), manifest(tmp_path, "new")
    changed = deepcopy(new)
    changed["episodes"][0]["candidate"] = "another-policy.py"
    with pytest.raises(ValueError, match="Episode candidate identity"):
        compare_manifests(old, changed, {"a": 1.0})
    changed = deepcopy(new)
    changed["hashes"]["source-new.py"] = "incorrect-source-hash"
    with pytest.raises(ValueError, match="hashes disagree"):
        compare_manifests(old, changed, {"a": 1.0})
    from pathlib import Path

    snapshot = Path(new["candidate_snapshot"])
    original_snapshot = snapshot.read_bytes()
    snapshot.write_bytes(gzip.compress(b"different source"))
    with pytest.raises(ValueError, match="hashes disagree"):
        compare_manifests(old, new, {"a": 1.0})
    snapshot.write_bytes(original_snapshot)
    Path(new["executed_candidate"]).write_bytes(b"changed frozen executable")
    with pytest.raises(ValueError, match="hashes disagree"):
        compare_manifests(old, new, {"a": 1.0})
