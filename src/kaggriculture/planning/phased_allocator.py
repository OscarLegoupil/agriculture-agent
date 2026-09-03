"""Phased resource allocator.

Extends the static, single-shot `allocate()` with the two axes needed to
scale a farm from a handful of tiles to a real land-and-hire expansion:

1. Land purchases. The tile budget is itself a decision: NE, SW, SE unlock
   in that fixed order (see `LAND_ORDER`) at increasing prices, and each
   unlock jumps the tile budget by one quadrant (25 tiles).
2. Worker capacity. Assigning tiles to a farmer + hands is not free. Each
   worker can sustainably service a bounded number of tile-actions per day
   (water, harvest, feed, care) before travel time between tiles eats the
   day. A phase's crop-and-animal footprint must not exceed what its hired
   worker count can actually tend.

This module does not decide route logic (that is the scheduler, see
`kaggriculture.agent.route_agent`). It decides what the farm should look
like at each phase boundary: how many tiles of which crop, which animals,
when to buy land, and how many hands the phase needs. Phase boundaries are
placed at every land buy day, every hire-ramp change day, and the season
start/end; within each phase the static allocator is re-run over that
phase's own duration and tile budget.
"""

from __future__ import annotations

from dataclasses import dataclass
from itertools import pairwise
from typing import Final

from kaggriculture.env.constants import LAND_ORDER, LAND_PRICES
from kaggriculture.planning.allocator import Allocation, allocate

# One worker's sustainable tile-actions-per-day budget (water/harvest/feed/care
# plus travel) on a 24-turn day. This is a conservative planning assumption,
# not a simulator constant; the scheduler (M8-scale-b) is the ground truth and
# this number should be revisited if its integration tests disagree.
TILES_PER_WORKER_PER_DAY: Final[int] = 8

QUADRANT_TILES: Final[int] = 25  # 5x5 tiles per quadrant


def _fib_hire_cost(n_hires: int) -> int:
    """Total coins to hire `n_hires` hands fresh in one day.

    HIRE cost is `fib(hires_today)` with fib(0)=1, fib(1)=1, fib(2)=2, ...,
    and resets every day, so hiring the same N hands daily costs this sum
    every single day of the phase.
    """
    if n_hires <= 0:
        return 0
    a, b = 1, 1
    total = 0
    for _ in range(n_hires):
        total += a
        a, b = b, a + b
    return total


@dataclass(frozen=True, slots=True)
class LandBuyPlan:
    """One land purchase attached to the phase it takes effect in."""

    quadrant: str
    day: int
    cost: int


@dataclass(frozen=True, slots=True)
class Phase:
    """The farm's target footprint over one contiguous day range."""

    start_day: int
    end_day: int  # exclusive
    tiles: int
    hands: int
    allocation: Allocation
    land_buys: tuple[LandBuyPlan, ...] = ()

    @property
    def length_days(self) -> int:
        return self.end_day - self.start_day

    @property
    def worker_tile_demand(self) -> int:
        """Tiles needing a daily worker action: crops, wheat reserve, structures."""
        return (
            self.allocation.fill_crop_tiles
            + self.allocation.wheat_tiles
            + self.allocation.structure_tiles
        )

    @property
    def worker_capacity(self) -> int:
        return (1 + self.hands) * TILES_PER_WORKER_PER_DAY

    @property
    def daily_hire_cost(self) -> int:
        return _fib_hire_cost(self.hands)


@dataclass(frozen=True, slots=True)
class PhasedPlan:
    season_days: int
    phases: tuple[Phase, ...]


@dataclass(frozen=True, slots=True)
class OverSubscription:
    """One phase whose crop-and-animal footprint exceeds its worker capacity."""

    phase_index: int
    start_day: int
    end_day: int
    demand: int
    capacity: int


def _validate_land_buy_days(land_buy_days: dict[str, int]) -> None:
    unknown = set(land_buy_days) - set(LAND_ORDER)
    if unknown:
        raise ValueError(f"unknown quadrants {sorted(unknown)}, expected subset of {LAND_ORDER}")

    order_index = {q: i for i, q in enumerate(LAND_ORDER)}
    bought = sorted(land_buy_days, key=lambda q: order_index[q])
    expected_prefix = LAND_ORDER[: len(bought)]
    if tuple(bought) != expected_prefix:
        raise ValueError(f"land buys must be a prefix of {LAND_ORDER} in order; got {bought}")

    prev_day = -1
    for quadrant in expected_prefix:
        day = land_buy_days[quadrant]
        if day < 0:
            raise ValueError(f"land_buy_days[{quadrant!r}] must be >= 0, got {day}")
        if day < prev_day:
            raise ValueError(
                f"land buys must be non-decreasing in {LAND_ORDER}; "
                f"{quadrant} at day {day} precedes an earlier buy at day {prev_day}"
            )
        prev_day = day


def _validate_hire_ramp(hire_ramp: dict[int, int]) -> None:
    for day, hands in hire_ramp.items():
        if day < 0:
            raise ValueError(f"hire_ramp day must be >= 0, got {day}")
        if hands < 0:
            raise ValueError(f"hire_ramp hand target must be >= 0, got {hands}")


def _tiles_unlocked_at(day: int, land_buy_days: dict[str, int]) -> int:
    n_quadrants = 1 + sum(1 for d in land_buy_days.values() if d <= day)
    return n_quadrants * QUADRANT_TILES


def _hands_active_at(day: int, hire_ramp: dict[int, int]) -> int:
    applicable = [d for d in hire_ramp if d <= day]
    if not applicable:
        return 0
    return hire_ramp[max(applicable)]


def build_phased_plan(
    *,
    season_days: int,
    land_buy_days: dict[str, int] | None = None,
    hire_ramp: dict[int, int] | None = None,
    price_map: dict[str, float] | None = None,
    watered: bool = True,
    fertilized: bool = False,
    feed_cost_per_day: float = 25.0,
    max_animals_per_species: dict[str, int] | None = None,
) -> PhasedPlan:
    """Build a phased plan over `season_days` days.

    `land_buy_days` maps a quadrant ("NE", "SW", "SE") to the day it is
    bought; quadrants must be a prefix of `LAND_ORDER` bought in
    non-decreasing day order. `hire_ramp` maps a day to the target hand
    count active from that day forward (missing days inherit the most
    recent earlier target, defaulting to 0 before the first entry).

    Phase boundaries are the union of {0, season_days}, land buy days, and
    hire ramp change days. Each phase re-runs `allocate()` over its own tile
    budget and duration, so revenue for a phase is not double-counted
    against the season total the way calling `allocate()` once with the
    full remaining horizon would be.
    """
    if season_days < 1:
        raise ValueError(f"season_days must be >= 1, got {season_days}")
    land_buy_days = land_buy_days or {}
    hire_ramp = hire_ramp or {}
    _validate_land_buy_days(land_buy_days)
    _validate_hire_ramp(hire_ramp)

    boundaries = sorted({0, season_days, *land_buy_days.values(), *hire_ramp.keys()})
    boundaries = [b for b in boundaries if 0 <= b <= season_days]

    phases: list[Phase] = []
    for start, end in pairwise(boundaries):
        tiles = _tiles_unlocked_at(start, land_buy_days)
        hands = _hands_active_at(start, hire_ramp)
        allocation = allocate(
            tiles=tiles,
            horizon_days=end - start,
            price_map=price_map,
            watered=watered,
            fertilized=fertilized,
            feed_cost_per_day=feed_cost_per_day,
            max_animals_per_species=max_animals_per_species,
        )
        land_buys_here = tuple(
            LandBuyPlan(quadrant=q, day=d, cost=LAND_PRICES[LAND_ORDER.index(q)])
            for q, d in land_buy_days.items()
            if d == start
        )
        phases.append(
            Phase(
                start_day=start,
                end_day=end,
                tiles=tiles,
                hands=hands,
                allocation=allocation,
                land_buys=land_buys_here,
            )
        )

    return PhasedPlan(season_days=season_days, phases=tuple(phases))


def validate_worker_capacity(plan: PhasedPlan) -> list[OverSubscription]:
    """Return every phase whose footprint over-subscribes its worker capacity."""
    violations: list[OverSubscription] = []
    for i, phase in enumerate(plan.phases):
        if phase.worker_tile_demand > phase.worker_capacity:
            violations.append(
                OverSubscription(
                    phase_index=i,
                    start_day=phase.start_day,
                    end_day=phase.end_day,
                    demand=phase.worker_tile_demand,
                    capacity=phase.worker_capacity,
                )
            )
    return violations


def assert_worker_capacity(plan: PhasedPlan) -> None:
    """Raise ValueError with every violating phase if any phase is over-subscribed."""
    violations = validate_worker_capacity(plan)
    if not violations:
        return
    lines = "\n".join(
        f"  phase {v.phase_index} (day {v.start_day}-{v.end_day}): "
        f"demand {v.demand} tile-actions/day > capacity {v.capacity}"
        for v in violations
    )
    raise ValueError(f"plan over-subscribes worker-turns:\n{lines}")
