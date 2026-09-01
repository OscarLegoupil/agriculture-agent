"""Dynamic re-planner.

Wraps the static allocator with a state machine that triggers a re-plan
when observed market prices diverge from the working forecast by more than
a configurable relative threshold. This keeps allocation decisions
reactive without paying the cost of an allocation call every turn.

Contract:

- The caller advances the planner with ``step(day, observed_prices)`` on
  whatever cadence they choose (usually once per day at end-of-day price
  update).
- Each step compares the observed prices to the working forecast. If the
  maximum relative deviation exceeds ``threshold_pct``, a re-plan is
  triggered: the observed prices become the new forecast, the allocator is
  called with the shortened remaining horizon, and a ``ReplanEvent`` is
  logged.
- ``events`` and ``replan_frequency`` expose telemetry so the harness can
  report how often re-planning fires.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from kaggriculture.planning.allocator import Allocation, allocate


@dataclass(frozen=True, slots=True)
class ReplanEvent:
    """One re-plan trigger."""

    day: int
    max_deviation: float
    triggering_resource: str
    old_allocation: Allocation
    new_allocation: Allocation


def max_relative_deviation(
    observed: dict[str, float], forecast: dict[str, float]
) -> tuple[float, str | None]:
    """Return the largest |observed / forecast - 1| across shared resources.

    Resources missing from either dict are skipped. A zero forecast for a
    resource is treated as a full-scale (1.0) deviation to force a re-plan
    when the caller's forecast is uninformative.
    """
    worst = 0.0
    culprit: str | None = None
    for resource, obs in observed.items():
        if resource not in forecast:
            continue
        fcst = forecast[resource]
        dev = 1.0 if fcst <= 0 else abs(obs / fcst - 1.0)
        if dev > worst:
            worst = dev
            culprit = resource
    return worst, culprit


@dataclass
class DynamicReplanner:
    """Stateful allocator that re-plans when price forecasts drift."""

    tiles: int
    season_days: int
    initial_forecast: dict[str, float]
    threshold_pct: float = 0.15
    watered: bool = True
    fertilized: bool = False
    feed_cost_per_day: float = 25.0
    max_animals_per_species: dict[str, int] | None = None
    events: list[ReplanEvent] = field(default_factory=list)
    _forecast: dict[str, float] = field(init=False)
    _allocation: Allocation = field(init=False)
    _last_step_day: int = field(init=False, default=0)

    def __post_init__(self) -> None:
        if self.threshold_pct < 0:
            raise ValueError(f"threshold_pct must be >= 0, got {self.threshold_pct}")
        if self.tiles < 0:
            raise ValueError(f"tiles must be >= 0, got {self.tiles}")
        if self.season_days < 1:
            raise ValueError(f"season_days must be >= 1, got {self.season_days}")
        self._forecast = dict(self.initial_forecast)
        self._allocation = allocate(
            tiles=self.tiles,
            horizon_days=self.season_days,
            price_map=self._forecast,
            watered=self.watered,
            fertilized=self.fertilized,
            feed_cost_per_day=self.feed_cost_per_day,
            max_animals_per_species=self.max_animals_per_species,
        )

    @property
    def allocation(self) -> Allocation:
        return self._allocation

    @property
    def forecast(self) -> dict[str, float]:
        return dict(self._forecast)

    @property
    def replan_frequency(self) -> float:
        """Re-plans per observed day since construction."""
        if self._last_step_day <= 0:
            return 0.0
        return len(self.events) / self._last_step_day

    def step(self, day: int, observed_prices: dict[str, float]) -> ReplanEvent | None:
        """Advance one observation. Returns a ReplanEvent iff a re-plan fired."""
        if day < 0:
            raise ValueError(f"day must be >= 0, got {day}")
        if day > self.season_days:
            raise ValueError(f"day {day} exceeds season_days {self.season_days}")
        self._last_step_day = max(self._last_step_day, day)
        deviation, culprit = max_relative_deviation(observed_prices, self._forecast)
        if deviation < self.threshold_pct or culprit is None:
            return None
        remaining = max(1, self.season_days - day)
        new_forecast = {**self._forecast, **observed_prices}
        new_alloc = allocate(
            tiles=self.tiles,
            horizon_days=remaining,
            price_map=new_forecast,
            watered=self.watered,
            fertilized=self.fertilized,
            feed_cost_per_day=self.feed_cost_per_day,
            max_animals_per_species=self.max_animals_per_species,
        )
        event = ReplanEvent(
            day=day,
            max_deviation=deviation,
            triggering_resource=culprit,
            old_allocation=self._allocation,
            new_allocation=new_alloc,
        )
        self.events.append(event)
        self._forecast = new_forecast
        self._allocation = new_alloc
        return event
