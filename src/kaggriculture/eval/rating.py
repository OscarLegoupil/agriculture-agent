"""Elo and Bradley-Terry rating for agent evaluation.

Two mechanisms, one input format (a list of `(agent_a, agent_b, result_a)`
tuples where result is 1 for a-win, 0 for b-win, 0.5 for tie).

Elo is sequential and matches Kaggle's live-ladder behavior: each match updates
both ratings by `K * (result - expected)`. Bradley-Terry is a batch MLE over
the full match log and matches Kaggle's final tournament: it produces strengths
that maximize `P(observed outcomes)` under the logistic model.

For our internal A/B tests we default to Bradley-Terry because it does not
suffer from path dependence, but the Elo trajectory is useful for diagnosing
noise.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass

from kaggriculture.eval.runner import EpisodeResult

ELO_DEFAULT_START = 1500.0
ELO_DEFAULT_K = 32.0


@dataclass(frozen=True, slots=True)
class Match:
    """One episode outcome flattened to `(a, b, result_a)` form. result_a in {0, 0.5, 1}."""

    agent_a: str
    agent_b: str
    result_a: float


def episodes_to_matches(results: Sequence[EpisodeResult]) -> list[Match]:
    matches: list[Match] = []
    for r in results:
        winner = r.winner  # "a" | "b" | None
        result_a = 0.5 if winner is None else (1.0 if winner == "a" else 0.0)
        matches.append(Match(r.agent_a, r.agent_b, result_a))
    return matches


def elo_expected(rating_a: float, rating_b: float) -> float:
    """Expected score for A against B under the standard Elo curve."""
    return float(1.0 / (1.0 + 10.0 ** ((rating_b - rating_a) / 400.0)))


def elo_update(
    rating_a: float,
    rating_b: float,
    result_a: float,
    k: float = ELO_DEFAULT_K,
) -> tuple[float, float]:
    expected_a = elo_expected(rating_a, rating_b)
    delta = k * (result_a - expected_a)
    return rating_a + delta, rating_b - delta


def elo_ratings(
    matches: Sequence[Match],
    *,
    start: float = ELO_DEFAULT_START,
    k: float = ELO_DEFAULT_K,
) -> dict[str, float]:
    """Sequential Elo over `matches` in order. Returns final ratings per agent."""
    ratings: dict[str, float] = {}
    for m in matches:
        ra = ratings.setdefault(m.agent_a, start)
        rb = ratings.setdefault(m.agent_b, start)
        ratings[m.agent_a], ratings[m.agent_b] = elo_update(ra, rb, m.result_a, k=k)
    return ratings


def elo_trajectory(
    matches: Sequence[Match],
    *,
    start: float = ELO_DEFAULT_START,
    k: float = ELO_DEFAULT_K,
) -> dict[str, list[float]]:
    """Elo history per agent (one entry per match involving that agent)."""
    ratings: dict[str, float] = {}
    history: dict[str, list[float]] = {}
    for m in matches:
        ra = ratings.setdefault(m.agent_a, start)
        rb = ratings.setdefault(m.agent_b, start)
        ratings[m.agent_a], ratings[m.agent_b] = elo_update(ra, rb, m.result_a, k=k)
        history.setdefault(m.agent_a, []).append(ratings[m.agent_a])
        history.setdefault(m.agent_b, []).append(ratings[m.agent_b])
    return history


def bradley_terry_fit(
    matches: Sequence[Match],
    *,
    iterations: int = 1000,
    tol: float = 1e-8,
    anchor: str | None = None,
) -> dict[str, float]:
    """Return log-strengths from Zermelo's algorithm for the Bradley-Terry MLE.

    Ties are split as half-win to each side. `anchor` (if given) is fixed at 0
    to break the additive gauge; otherwise strengths are recentered on mean 0.
    """
    agents = sorted({m.agent_a for m in matches} | {m.agent_b for m in matches})
    if len(agents) < 2:
        return dict.fromkeys(agents, 0.0)

    # Wins: total half-wins each agent accumulates.
    wins = dict.fromkeys(agents, 0.0)
    # Pairwise match counts.
    n_pairwise: dict[tuple[str, str], int] = {}
    for m in matches:
        wins[m.agent_a] += m.result_a
        wins[m.agent_b] += 1.0 - m.result_a
        key = (m.agent_a, m.agent_b) if m.agent_a < m.agent_b else (m.agent_b, m.agent_a)
        n_pairwise[key] = n_pairwise.get(key, 0) + 1

    # Zermelo iteration on positive strengths pi, then log at the end.
    strengths = dict.fromkeys(agents, 1.0)
    for _ in range(iterations):
        new_strengths: dict[str, float] = {}
        max_delta = 0.0
        for i in agents:
            denom = 0.0
            for j in agents:
                if i == j:
                    continue
                key = (i, j) if i < j else (j, i)
                n_ij = n_pairwise.get(key, 0)
                if n_ij == 0:
                    continue
                denom += n_ij / (strengths[i] + strengths[j])
            if denom == 0 or wins[i] == 0:
                new_strengths[i] = strengths[i]
            else:
                new_strengths[i] = wins[i] / denom
            max_delta = max(max_delta, abs(new_strengths[i] - strengths[i]))
        strengths = new_strengths
        if max_delta < tol:
            break

    log_strengths = {a: math.log(s) if s > 0 else float("-inf") for a, s in strengths.items()}
    if anchor is not None and anchor in log_strengths:
        offset = log_strengths[anchor]
        log_strengths = {a: v - offset for a, v in log_strengths.items()}
    else:
        finite = [v for v in log_strengths.values() if math.isfinite(v)]
        if finite:
            mean = sum(finite) / len(finite)
            log_strengths = {a: v - mean for a, v in log_strengths.items()}
    return log_strengths


def bradley_terry_to_elo_scale(log_strengths: dict[str, float]) -> dict[str, float]:
    """Convert BT log-strengths to Elo-like ratings (mean 1500, 400/ln(10) scale)."""
    scale = 400.0 / math.log(10.0)
    return {a: ELO_DEFAULT_START + v * scale for a, v in log_strengths.items()}
