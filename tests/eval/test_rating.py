"""Tests for Elo and Bradley-Terry rating."""

from __future__ import annotations

import math

from kaggriculture.eval import (
    Match,
    bradley_terry_fit,
    bradley_terry_to_elo_scale,
    elo_expected,
    elo_ratings,
    elo_update,
)


def test_elo_expected_symmetric() -> None:
    # Equal ratings: 50/50 expected score.
    assert elo_expected(1500, 1500) == 0.5
    # +400 advantage yields ~90.9% expected.
    assert abs(elo_expected(1900, 1500) - 10 / 11) < 1e-9


def test_elo_update_zero_sum() -> None:
    a1, b1 = elo_update(1500, 1500, result_a=1.0, k=32)
    # Sum of ratings is invariant under any Elo update.
    assert abs((a1 + b1) - 3000.0) < 1e-9


def test_elo_ratings_over_dominant_agent() -> None:
    matches = [Match("strong", "weak", 1.0) for _ in range(100)]
    ratings = elo_ratings(matches)
    assert ratings["strong"] > ratings["weak"]
    # Sum invariant.
    assert abs(sum(ratings.values()) - 2 * 1500.0) < 1e-6


def test_bradley_terry_recovers_stronger_agent() -> None:
    # A wins 8/10 games; both agents are the only two.
    matches = [Match("A", "B", 1.0)] * 8 + [Match("A", "B", 0.0)] * 2
    strengths = bradley_terry_fit(matches)
    assert strengths["A"] > strengths["B"]
    # Ratio of probabilities matches wins ratio (approx).
    diff = strengths["A"] - strengths["B"]
    assert abs(math.exp(diff) - 4.0) < 1e-3  # 8:2 == 4:1


def test_bradley_terry_three_way_transitivity() -> None:
    # A dominates B, B dominates C.
    matches = (
        [Match("A", "B", 1.0)] * 10
        + [Match("B", "C", 1.0)] * 10
        + [Match("A", "C", 1.0)] * 5  # A wins direct too
    )
    strengths = bradley_terry_fit(matches)
    assert strengths["A"] > strengths["B"] > strengths["C"]


def test_bradley_terry_ties_are_half_wins() -> None:
    # Only ties: strengths should be equal (both around 0).
    matches = [Match("A", "B", 0.5)] * 20
    strengths = bradley_terry_fit(matches)
    assert abs(strengths["A"] - strengths["B"]) < 1e-6


def test_bt_to_elo_scale_preserves_ordering() -> None:
    strengths = {"strong": 1.5, "medium": 0.0, "weak": -1.5}
    elo = bradley_terry_to_elo_scale(strengths)
    assert elo["strong"] > elo["medium"] > elo["weak"]
    # Mean is 1500 by convention when strengths are mean-0.
    assert abs(elo["medium"] - 1500.0) < 1e-9
