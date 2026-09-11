"""Corrupted experiment evidence must not produce a competitive result."""

import gzip
import hashlib
from copy import deepcopy

import pytest
from scripts.breakthrough_report import verify


@pytest.fixture
def manifest(tmp_path):
    policy = tmp_path / "main.py"
    opponent = tmp_path / "opponent.py"
    snapshot = tmp_path / "policy.py.gz"
    content = b"def agent(obs): return {}\n"
    policy.write_bytes(content)
    opponent.write_bytes(content)
    snapshot.write_bytes(gzip.compress(content, mtime=0))
    digest = hashlib.sha256(content).hexdigest()
    return {
        "complete": True,
        "declared_panel": {"seeds": [0], "seats": [0, 1], "opponents": [str(opponent)]},
        "candidates": {str(policy): {"sha256": digest, "snapshot": str(snapshot)}},
        "hashes": {str(opponent): digest},
        "episodes": [
            dict(
                candidate=str(policy),
                opponent=str(opponent),
                seed=0,
                resolved_seed=0,
                seat=seat,
                cash=100,
                opponent_cash=100,
                statuses=["DONE", "DONE"],
                configuration={"seed": 0, "episodeSteps": 720},
            )
            for seat in (0, 1)
        ],
    }


@pytest.mark.parametrize(
    "defect", ["missing", "duplicate", "seed", "configuration", "cash", "hash"]
)
def test_corrupt_evidence_is_rejected(manifest, defect):
    assert verify(manifest)["episodeSteps"] == 720
    changed = deepcopy(manifest)
    if defect == "missing":
        changed["episodes"].pop()
    elif defect == "duplicate":
        changed["episodes"].append(deepcopy(changed["episodes"][0]))
    elif defect == "seed":
        changed["episodes"][0]["resolved_seed"] = 99
    elif defect == "configuration":
        changed["episodes"][0]["configuration"]["episodeSteps"] = 719
    elif defect == "cash":
        changed["episodes"][0]["cash"] = None
    else:
        changed["hashes"] = dict.fromkeys(changed["hashes"], "0" * 64)
    with pytest.raises(ValueError):
        verify(changed)


def test_changed_action_table_cannot_hide_behind_unchanged_main(manifest, tmp_path):
    sidecar = tmp_path / "actions.json"
    sidecar.write_bytes(b"[]")
    manifest["executable_bundles"] = {"opponent": {str(sidecar): hashlib.sha256(b"[]").hexdigest()}}
    verify(manifest)
    sidecar.write_bytes(b"[1]")
    with pytest.raises(ValueError, match="sidecar"):
        verify(manifest)
