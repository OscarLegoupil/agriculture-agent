"""Small statistical helpers for A/B testing.

Standalone so the harness does not pull in scipy for tests it does not need.
"""

from __future__ import annotations

import math


def wilson_ci(wins: int, n: int, z: float = 1.96) -> tuple[float, float]:
    """Wilson score confidence interval for a binomial proportion.

    z=1.96 gives 95% CI. Returns (lower, upper) both in [0, 1].
    """
    if n == 0:
        return 0.0, 0.0
    p = wins / n
    denom = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / denom
    margin = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denom
    lo = max(0.0, centre - margin)
    hi = min(1.0, centre + margin)
    return lo, hi


def _binom_cdf(k: int, n: int, p: float = 0.5) -> float:
    """P(X <= k) for X ~ Binomial(n, p). Exact via math.comb."""
    if k < 0:
        return 0.0
    if k >= n:
        return 1.0
    return sum(math.comb(n, i) * (p**i) * ((1 - p) ** (n - i)) for i in range(k + 1))


def sign_test_two_sided(wins: int, losses: int) -> float:
    """Two-sided sign test p-value under H0: P(win) = P(loss) = 0.5.

    Ties are excluded before calling. Returns 1.0 if wins + losses == 0.
    """
    n = wins + losses
    if n == 0:
        return 1.0
    lower = _binom_cdf(min(wins, losses), n, 0.5)
    return float(min(1.0, 2.0 * lower))
