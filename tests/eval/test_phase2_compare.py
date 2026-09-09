"""Matched inference must reject missing scenarios and retain paired dependence."""

from copy import deepcopy

import pytest
from scripts.phase2_compare import compare


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
