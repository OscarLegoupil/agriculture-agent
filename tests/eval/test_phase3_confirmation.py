"""Preregistered confirmation rejects jointly wrong but mutually matching panels."""

import gzip
import hashlib
from copy import deepcopy

import pytest
from scripts.phase3_confirmation import confirm


@pytest.fixture
def evidence(tmp_path):
    opponents = ["lonespear", "gzm", "seyam", "cok"]
    config = {"seed": None, "episodeSteps": 720, "turnsPerDay": 24, "actTimeout": 1}
    environment = {
        "environment_version": "fixture",
        "interpreter_sha256": "interpreter",
        "lock_sha256": "lock",
        "dependencies": {},
        "configuration": config,
    }
    protocol = {
        "schema_version": 1,
        "environment": environment,
        "opponent_hashes": {name: hashlib.sha256(name.encode()).hexdigest() for name in opponents},
        "pools": {
            "anchor": dict.fromkeys(opponents[:2], 0.5),
            "challenge": dict.fromkeys(opponents[2:], 0.5),
            "equal_four": dict.fromkeys(opponents, 0.25),
        },
        "splits": {"validation": [3000, 3001], "holdout": [20000, 20001]},
        "gates": {
            "anchor_min_delta": 0.05,
            "anchor_min_family_score": 0.4,
            "challenge_min_score": 0.5,
            "cok_opponent": "cok",
            "cok_min_score": 0.4,
            "equal_four_lower_min": 0.5,
            "max_action_seconds": 0.5,
        },
        "metadata": {"note": "Additional preregistration metadata is allowed"},
    }
    manifests = []
    for role, cash in (("incumbent", 0), ("challenger", 200)):
        raw = role.encode()
        source = tmp_path / (role + ".py")
        source.write_bytes(raw)
        snapshot = tmp_path / (role + ".py.gz")
        snapshot.write_bytes(gzip.compress(raw))
        digest = hashlib.sha256(raw).hexdigest()
        protocol[role + "_sha256"] = digest
        manifest = {
            "complete": True,
            "revision": "fixture",
            "arguments": {"candidate": str(source)},
            "executed_candidate": str(source),
            "candidate_snapshot": str(snapshot),
            "hashes": {**protocol["opponent_hashes"], str(source): digest},
            **{key: value for key, value in environment.items() if key != "configuration"},
            "episodes": [
                {
                    "candidate": str(source),
                    "opponent": opponent,
                    "seed": seed,
                    "seat": seat,
                    "resolved_seed": seed,
                    "configuration": deepcopy(config),
                    "cash": cash,
                    "opponent_cash": 100,
                    "statuses": ["DONE", "DONE"],
                    "stderr_turns": 0,
                    "runtime_p99_seconds": 0.002,
                    "runtime_max_seconds": 0.003,
                    "seconds": 1,
                }
                for opponent in opponents
                for seed in protocol["splits"]["validation"]
                for seat in (0, 1)
            ],
        }
        manifests.append(manifest)
    return protocol, *manifests


def test_complete_frozen_panel_passes_and_labels_runtime_scope(evidence):
    protocol, old, new = evidence
    report = confirm(protocol, "validation", old, new)
    assert report["statistical_runtime_gates_pass"]
    assert report["pools"]["equal_four"]["aggregate"]["challenger_score"] == 1
    assert report["telemetry"]["challenger"]["per_game_action_max_seconds"]["max"] == 0.003
    assert "not pooled" in report["telemetry"]["challenger"]["quantile_scope"]


@pytest.mark.parametrize(
    "mutation",
    [
        "truncated",
        "duplicate",
        "wrong_seed",
        "configuration",
        "identity",
        "interpreter",
        "opponent",
    ],
)
def test_jointly_matching_but_wrong_panels_are_rejected(evidence, mutation):
    protocol, old, new = evidence
    for manifest in (old, new):
        if mutation == "truncated":
            manifest["episodes"] = [e for e in manifest["episodes"] if e["seed"] == 3000]
        elif mutation == "duplicate":
            manifest["episodes"][-1] = deepcopy(manifest["episodes"][0])
        elif mutation == "wrong_seed":
            manifest["episodes"][0]["resolved_seed"] = 1234
        elif mutation == "configuration":
            manifest["episodes"][0]["configuration"]["episodeSteps"] = 718
        elif mutation == "identity":
            manifest["hashes"][manifest["arguments"]["candidate"]] = "0" * 64
        elif mutation == "interpreter":
            manifest["interpreter_sha256"] = "jointly-wrong"
        elif mutation == "opponent":
            manifest["hashes"]["cok"] = "jointly-wrong"
    with pytest.raises(ValueError):
        confirm(protocol, "validation", old, new)


def test_holdout_cannot_accidentally_reuse_validation_panel(evidence):
    protocol, old, new = evidence
    with pytest.raises(ValueError, match="Cartesian"):
        confirm(protocol, "holdout", old, new)


def test_error_is_a_failed_gate_and_remains_in_denominator(evidence):
    protocol, old, new = evidence
    row = new["episodes"][0]
    row["cash"] = None
    row["statuses"][row["seat"]] = "TIMEOUT"
    report = confirm(protocol, "validation", old, new)
    assert not report["gates"]["candidate_errors_zero"]
    assert not report["statistical_runtime_gates_pass"]
    assert report["pools"]["anchor"]["opponents"]["lonespear"]["games"] == 4
    assert report["pools"]["anchor"]["opponents"]["lonespear"]["challenger_score"] == 0.75


@pytest.mark.parametrize("cash", [None, float("nan"), float("inf")])
def test_done_rows_require_finite_cash(evidence, cash):
    protocol, old, new = evidence
    new["episodes"][0]["cash"] = cash
    with pytest.raises(ValueError, match="DONE outcome"):
        confirm(protocol, "validation", old, new)


def test_cok_floor_and_runtime_are_independent_gates(evidence):
    protocol, old, new = evidence
    for row in new["episodes"]:
        if row["opponent"] == "cok":
            row["cash"] = 0
    new["episodes"][0]["runtime_max_seconds"] = 0.5
    report = confirm(protocol, "validation", old, new)
    assert report["gates"]["challenge_score_floor"]
    assert not report["gates"]["cok_score_floor"]
    assert not report["gates"]["local_runtime_headroom"]


def test_protocol_cannot_weaken_inherited_gates_or_overlap_splits(evidence):
    protocol, old, new = evidence
    changed = deepcopy(protocol)
    changed["gates"]["anchor_min_delta"] = 0.01
    with pytest.raises(ValueError, match="weakened"):
        confirm(changed, "validation", old, new)
    changed = deepcopy(protocol)
    changed["splits"]["holdout"] = [3000]
    with pytest.raises(ValueError, match="overlaps"):
        confirm(changed, "validation", old, new)
