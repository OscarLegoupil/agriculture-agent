"""Wheat feed budget planner.

Given a projected animal roster over the season, compute the daily wheat
demand and the sustained wheat production capacity needed to feed it. The
output feeds the resource allocator and the market policy: too few wheat
tiles starves animals, too many burns tile-days that could grow premium
crops.

Feeding rules (from the simulator):

- Each surviving animal consumes 1 wheat per day.
- Feed is required starting the day after purchase; a newly bought animal
  does not need to be fed on its arrival day.
- Two consecutive unfed days makes the animal escape, so the planner must
  size for the peak, not the average.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass

from kaggriculture.planning.crop_roi import lifecycle_units_and_days


@dataclass(frozen=True, slots=True)
class AnimalPlan:
    """One line-item in the projected roster."""

    animal: str
    purchase_day: int
    count: int = 1

    def __post_init__(self) -> None:
        if self.count < 1:
            raise ValueError(f"count must be >= 1, got {self.count}")
        if self.purchase_day < 0:
            raise ValueError(f"purchase_day must be >= 0, got {self.purchase_day}")


@dataclass(frozen=True, slots=True)
class FeedBudget:
    """Feed-demand projection over the season."""

    daily_demand: tuple[int, ...]
    peak_daily_demand: int
    total_wheat: int
    target_daily_harvest: int
    tiles_needed: int
    wheat_lifecycle_units: int
    wheat_lifecycle_days: int


def daily_wheat_demand(roster: Sequence[AnimalPlan], *, season_days: int = 30) -> tuple[int, ...]:
    """Wheat demand per day across ``season_days + 1`` days (day 0 to day N)."""
    if season_days < 0:
        raise ValueError(f"season_days must be >= 0, got {season_days}")
    demand = [0] * (season_days + 1)
    for plan in roster:
        first_feed_day = plan.purchase_day + 1
        if first_feed_day > season_days:
            continue
        for day in range(first_feed_day, season_days + 1):
            demand[day] += plan.count
    return tuple(demand)


def feed_budget(
    roster: Sequence[AnimalPlan],
    *,
    season_days: int = 30,
    wheat_watered: bool = True,
    wheat_fertilized: bool = False,
) -> FeedBudget:
    """Sizing decision: how many wheat tiles the farm must run to feed the roster.

    Peak daily demand sets the sustained harvest rate; tile count divides that
    rate by the per-tile-per-day wheat yield derived from
    ``kaggriculture.planning.crop_roi.lifecycle_units_and_days``.
    """
    demand = daily_wheat_demand(roster, season_days=season_days)
    peak = max(demand) if demand else 0
    total = sum(demand)
    units, days = lifecycle_units_and_days(
        "WHEAT", watered=wheat_watered, fertilized=wheat_fertilized
    )
    per_tile_per_day = units / max(1, days)
    tiles = 0 if peak == 0 else math.ceil(peak / per_tile_per_day)
    return FeedBudget(
        daily_demand=demand,
        peak_daily_demand=peak,
        total_wheat=total,
        target_daily_harvest=peak,
        tiles_needed=tiles,
        wheat_lifecycle_units=units,
        wheat_lifecycle_days=days,
    )
