"""Public-state route selector.

A ``RouteSelector`` holds a small portfolio of route+micro agents and
dispatches each turn's observation to one active member. Selection
happens once at the end of the second in-game day using signals from the
shared opponent inventory tracker. Portfolio members must share the same
physical setup (tile assignments, structures, hands) so the switch is
consistent with actions already emitted.

The default portfolio is:

- ``v4_baseline``: the M7-a baseline route.
- ``v4_wheat_agg``: lower wheat and carrot sell thresholds, earlier
  route-level liquidate. Chosen against opponents that are stockpiling
  premium products and likely to flood the market late.
- ``v4_premium_hold``: higher egg sell threshold and larger wheat
  stockpile. Chosen against opponents that skip animals entirely.
- ``v4_early_tail``: earlier route-level tail liquidation. Chosen as the
  fallback family for the "unknown / broad" opponent bucket.

The selector's exposed telemetry (``chosen_key``, ``switches``) makes it
easy to A/B individual heuristics.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from typing import Any

from kaggriculture.env.observation import Observation, Structure
from kaggriculture.opponent.inference import OpponentInventoryTracker

Portfolio = dict[str, Callable[[dict[str, Any]], dict[str, Any]]]


@dataclass
class SelectorSignals:
    """Public-state features consumed by the default heuristic."""

    egg_upper: int
    milk_upper: int
    wool_upper: int
    opponent_has_animal: bool
    opponent_bought_land: bool


def default_heuristic(sig: SelectorSignals) -> str:
    """Map opponent-family signals to a portfolio key.

    Ordering: premium-glut warnings win over structural signals so the
    market rule fires even when the opponent has a coop. The fallback
    is ``v4_early_tail``: against an "unknown / broad" opponent, tighter
    late-game liquidation captures value that ``v4_baseline`` leaves on
    the table.
    """
    if sig.egg_upper > 20 or sig.milk_upper > 6 or sig.wool_upper > 6:
        return "v4_wheat_agg"
    if not sig.opponent_has_animal:
        return "v4_premium_hold"
    if sig.opponent_bought_land:
        return "v4_early_tail"
    return "v4_early_tail"


def extract_signals(obs: Observation, tracker: OpponentInventoryTracker) -> SelectorSignals:
    est = tracker.estimates
    opp = obs.opponent
    opp_has_animal = any(
        isinstance(t, Structure) and t.animal is not None for row in opp.tiles for t in row
    )
    opp_land = len(opp.unlocked_quadrants) > 1
    return SelectorSignals(
        egg_upper=est["EGG"].upper_bound,
        milk_upper=est["MILK"].upper_bound,
        wool_upper=est["WOOL"].upper_bound,
        opponent_has_animal=opp_has_animal,
        opponent_bought_land=opp_land,
    )


@dataclass
class RouteSelector:
    portfolio: Portfolio
    default_key: str
    decision_day: int = 3
    heuristic: Callable[[SelectorSignals], str] = field(default=default_heuristic)
    tracker: OpponentInventoryTracker = field(default_factory=OpponentInventoryTracker)

    chosen_key: str = field(init=False)
    switches: int = field(default=0, init=False)
    _decided: bool = field(default=False, init=False)
    _last_step: int = field(default=-1, init=False)

    def __post_init__(self) -> None:
        if self.default_key not in self.portfolio:
            raise KeyError(f"default_key {self.default_key!r} not in portfolio")
        self.chosen_key = self.default_key

    def __call__(self, obs_raw: dict[str, Any]) -> dict[str, Any]:
        obs = Observation.from_dict(obs_raw)
        if obs.step < self._last_step:
            self._reset()
        self._last_step = obs.step
        self.tracker.update(obs)
        if not self._decided and obs.day >= self.decision_day:
            sig = extract_signals(obs, self.tracker)
            new_key = self.heuristic(sig)
            if new_key not in self.portfolio:
                new_key = self.default_key
            if new_key != self.chosen_key:
                self.chosen_key = new_key
                self.switches += 1
            self._decided = True
        return self.portfolio[self.chosen_key](obs_raw)

    def _reset(self) -> None:
        self.tracker = OpponentInventoryTracker(
            max_orders_per_turn=self.tracker.max_orders_per_turn,
            shed_capacity=self.tracker.shed_capacity,
        )
        self.chosen_key = self.default_key
        self.switches = 0
        self._decided = False


def build_default_selector(
    portfolio: Portfolio,
    default_key: str = "v4_baseline",
    decision_day: int = 3,
) -> Callable[[dict[str, Any]], dict[str, Any]]:
    """Return a plain agent(obs) closure over a persistent RouteSelector."""
    selector = RouteSelector(
        portfolio=portfolio,
        default_key=default_key,
        decision_day=decision_day,
    )

    def agent(obs: dict[str, Any]) -> dict[str, Any]:
        return selector(obs)

    agent.selector = selector  # type: ignore[attr-defined]
    return agent


def portfolio_from_yaml_paths(
    yaml_paths: Iterable[str],
    micro_kwargs: dict[str, Any] | None = None,
) -> Portfolio:
    """Load a set of route YAMLs and wrap each in the micro-controller."""
    from kaggriculture.agent.route_agent.loader import load_route
    from kaggriculture.agent.route_agent.micro import wrap_with_micro
    from kaggriculture.agent.route_agent.runner import RouteAgent

    portfolio: Portfolio = {}
    kwargs = micro_kwargs or {}
    for path in yaml_paths:
        route = load_route(path)
        ra = RouteAgent(route)
        thresholds = dict(route.market_policy.sell_min_price)

        def _base(obs: dict[str, Any], _ra: RouteAgent = ra) -> dict[str, Any]:
            return _ra(obs)

        portfolio[route.name] = wrap_with_micro(
            _base,
            sell_thresholds=thresholds,
            **kwargs,
        )
    return portfolio
