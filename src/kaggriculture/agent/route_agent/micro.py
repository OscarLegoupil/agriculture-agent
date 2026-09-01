"""Micro-controller that layers M6 forecast + opponent tracker on a route agent.

The route agent handles physical actions (tile assignments, animal care,
crop rotation, hire schedule) and the base market policy. The micro layer
inspects near-term price forecasts and opponent stock estimates each turn
and can add extra SELL entries when the forecaster predicts a hard drop
or a salvage opportunity that the route policy would miss.

Design notes:

- Tile actions are never overridden. v4's flow is already tuned; changing
  physical actions has a high risk of net-negative A/Bs.
- Only additive market overrides are emitted. The route's thresholds stay
  the floor; the micro layer only pulls sells forward, never delays them.
- The M5 allocator / replanner is intentionally not called each turn: its
  outputs are already baked into the route's sell thresholds and tile
  assignments. Later routes can pass an updated ``sell_thresholds`` dict
  if they want intra-episode re-planning.
- Per-episode state (forecaster, tracker) is reset when the observation
  step index moves backwards, so re-using the module across episodes in a
  worker pool does not leak state.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from kaggriculture.env.constants import PRICE_FLOOR, PRODUCTS
from kaggriculture.env.observation import Observation
from kaggriculture.market.forecaster import PriceForecaster
from kaggriculture.opponent.inference import OpponentInventoryTracker


@dataclass
class MicroController:
    """Wraps a `base_agent` and overlays forecast-driven market overrides.

    ``lookahead_days``: how far ahead the forecaster looks when deciding
    to pull a sell forward. 2 days keeps the tracker's town-consumption
    projection exact (shops unlock at end of day and are stable within
    a 2-day horizon).

    ``drop_ratio``: hard-drop rule. Sell now if predicted future price
    < ``drop_ratio * p_now``.

    ``salvage_ratio``: forecast-salvage rule. If the product's current
    price is below the route's hold threshold and the forecaster expects
    it to fall further by at least ``1 - salvage_ratio``, sell now.

    ``tail_start_day``: tail-salvage rule. Once ``obs.day >= tail_start_day``,
    every product with ``p_now >= tail_floor`` is sold (up to the shed
    stock). This turns v4's "hold-then-liquidate" tail into a graded
    salvage as the last-day floor risk grows.

    ``tail_floor``: minimum sell price during the tail window.

    ``min_current_price``: skip all three rules when current price is
    close to the price floor; dumping into the floor has no upside.

    ``sell_thresholds``: optional route-provided per-product hold price. A
    product priced below its threshold is a salvage candidate. Products
    with no entry are excluded from the salvage rule.

    ``hard_budget_seconds``: per-turn wall clock cap for the whole micro
    path. If exceeded on the M6 update, return the base action untouched.
    """

    base_agent: Callable[[dict[str, Any]], dict[str, Any]]
    lookahead_days: int = 2
    drop_ratio: float = 0.7
    salvage_ratio: float = 0.9
    tail_start_day: int = 25
    tail_floor: int = PRICE_FLOOR + 4
    min_current_price: int = PRICE_FLOOR + 4
    sell_thresholds: dict[str, int] = field(default_factory=dict)
    hard_budget_seconds: float = 0.4

    forecaster: PriceForecaster = field(default_factory=PriceForecaster)
    tracker: OpponentInventoryTracker = field(default_factory=OpponentInventoryTracker)

    _last_step: int = field(default=-1, init=False)
    slowest_turn_seconds: float = field(default=0.0, init=False)
    overrides_added: int = field(default=0, init=False)

    def __call__(self, obs_raw: dict[str, Any]) -> dict[str, Any]:
        start = time.perf_counter()
        base = self.base_agent(obs_raw)
        try:
            obs = Observation.from_dict(obs_raw)
        except Exception:
            self._record_time(start)
            return base

        self._maybe_reset(obs)
        self.forecaster.update(obs)
        self.tracker.update(obs)

        if time.perf_counter() - start > self.hard_budget_seconds:
            self._record_time(start)
            return base

        market = list(base.get("market", []))
        added = self._forecast_early_sells(obs, market)
        self.overrides_added += added
        self._record_time(start)
        return {
            "farmer": base["farmer"],
            "hands": base["hands"],
            "market": market,
        }

    def _maybe_reset(self, obs: Observation) -> None:
        if obs.step < self._last_step:
            self.forecaster = PriceForecaster(smoothing=self.forecaster.smoothing)
            self.tracker = OpponentInventoryTracker(
                max_orders_per_turn=self.tracker.max_orders_per_turn,
                shed_capacity=self.tracker.shed_capacity,
            )
            self.overrides_added = 0
            self.slowest_turn_seconds = 0.0
        self._last_step = obs.step

    def _forecast_early_sells(self, obs: Observation, market: list[list[Any]]) -> int:
        prices_future = self.forecaster.predict_days(obs, self.lookahead_days)
        return apply_early_sell_overrides(
            market=market,
            shed=obs.private.shed,
            prices_now=obs.market.prices,
            prices_future=prices_future,
            drop_ratio=self.drop_ratio,
            min_current_price=self.min_current_price,
            salvage_ratio=self.salvage_ratio,
            sell_thresholds=self.sell_thresholds,
            day=obs.day,
            tail_start_day=self.tail_start_day,
            tail_floor=self.tail_floor,
        )

    def _record_time(self, start: float) -> None:
        elapsed = time.perf_counter() - start
        if elapsed > self.slowest_turn_seconds:
            self.slowest_turn_seconds = elapsed


def wrap_with_micro(
    base_agent: Callable[[dict[str, Any]], dict[str, Any]],
    **kwargs: Any,
) -> Callable[[dict[str, Any]], dict[str, Any]]:
    """Return a plain agent(obs) callable that runs base_agent then the micro layer.

    The returned closure holds a persistent ``MicroController`` on its
    ``controller`` attribute so callers can inspect telemetry after an
    episode (``slowest_turn_seconds``, ``overrides_added``).
    """
    controller = MicroController(base_agent=base_agent, **kwargs)

    def agent(obs: dict[str, Any]) -> dict[str, Any]:
        return controller(obs)

    agent.controller = controller  # type: ignore[attr-defined]
    return agent


def micro_agent_from_yaml(
    path: str | Path, **kwargs: Any
) -> Callable[[dict[str, Any]], dict[str, Any]]:
    """Load a route YAML and return a micro-wrapped agent, threading the route
    sell thresholds into the salvage rule.
    """
    from kaggriculture.agent.route_agent.loader import load_route
    from kaggriculture.agent.route_agent.runner import RouteAgent

    route = load_route(path)
    ra = RouteAgent(route)
    thresholds = dict(route.market_policy.sell_min_price)
    kwargs.setdefault("sell_thresholds", thresholds)
    return wrap_with_micro(lambda obs: ra(obs), **kwargs)


def apply_early_sell_overrides(
    *,
    market: list[list[Any]],
    shed: dict[str, int],
    prices_now: dict[str, int],
    prices_future: dict[str, float],
    drop_ratio: float,
    min_current_price: int,
    salvage_ratio: float = 0.9,
    sell_thresholds: dict[str, int] | None = None,
    day: int = 0,
    tail_start_day: int = 25,
    tail_floor: int = PRICE_FLOOR + 4,
) -> int:
    """Append SELL entries for products whose forecast price is set to drop.

    Three rules run per product, in order:

    1. ``drop_ratio``: sell now if predicted future price is a hard drop
       below the current price (e.g. below 70% of it).
    2. ``salvage_ratio``: if the current price is below the route's hold
       threshold and the forecast keeps it below current, take the
       salvage now instead of hoping for a rebound to the threshold.
    3. Tail salvage: once ``day >= tail_start_day``, any stock priced
       above ``tail_floor`` is sold. This graded liquidation captures
       above-floor prices before the whole market dumps on the last day.

    Mutates ``market`` in place. Returns the number of entries added. The
    function never removes existing entries and never adds a SELL for a
    product that already has one in ``market``.
    """
    thresholds = sell_thresholds or {}
    already_selling = {
        (m[0], m[1]) for m in market if isinstance(m, list) and len(m) >= 2 and m[0] == "SELL"
    }
    tail_active = day >= tail_start_day
    added = 0
    for product in PRODUCTS:
        if ("SELL", product) in already_selling:
            continue
        n = int(shed.get(product, 0))
        if n <= 0:
            continue
        p_now = int(prices_now.get(product, 0))
        if p_now < min_current_price:
            continue
        p_future = float(prices_future.get(product, 0.0))
        threshold = thresholds.get(product)
        hard_drop = p_future < drop_ratio * p_now
        salvage = threshold is not None and p_now < threshold and p_future < salvage_ratio * p_now
        tail = tail_active and p_now >= tail_floor
        if hard_drop or salvage or tail:
            market.append(["SELL", product, n])
            added += 1
    return added
