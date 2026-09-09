"""Explicit subset comparisons cannot silently discard missing paired seats."""

import pytest
from scripts.phase4_compare import subset


def test_missing_seat_is_rejected():
    manifest = {"episodes": [{"opponent": "x", "seed": 1, "seat": 0, "resolved_seed": 1}]}
    with pytest.raises(ValueError, match="missing scenarios"):
        subset(manifest, ["x"], [1])


def test_subset_preserves_parent_and_rejects_seed_mismatch():
    rows = [
        {"opponent": "x", "seed": seed, "seat": seat, "resolved_seed": seed}
        for seed in (1, 2)
        for seat in (0, 1)
    ]
    parent = {"episodes": rows, "complete": True, "revision": "frozen"}
    result = subset(parent, ["x"], [2])
    assert result["revision"] == "frozen" and len(result["episodes"]) == 2
    assert len(parent["episodes"]) == 4
    rows[-1]["resolved_seed"] = 99
    with pytest.raises(ValueError, match="Resolved seed"):
        subset(parent, ["x"], [2])
