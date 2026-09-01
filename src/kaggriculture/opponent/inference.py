"""Opponent inventory inference from public state.

The tracker consumes a stream of :class:`Observation` snapshots (one per turn)
and maintains a running estimate of the opponent's holdings for each traded
commodity. Three signals are combined every turn:

- **Market ledger.** The market inventory changes by exactly one unit per
  ``SELL`` (when the sale price is above the floor) and per ``BUY_PRODUCT``.
  Subtracting our own contribution and the deterministic town consumption
  from the observed market delta gives the opponent's net trade activity.
- **Opponent farm.** Harvests and feeds are visible from tile deltas on the
  opponent's board. Harvests raise opp holdings; wheat feeds and fertilizer
  applications lower them.
- **Sale-at-floor slack.** When ``market_price`` equals ``PRICE_FLOOR`` for a
  commodity, opponent sells at floor do not touch the market inventory
  (``kaggriculture.py`` guards ``market["inventory"][item] += 1`` on
  ``price > 1``). Every such turn widens the interval between the lower and
  upper bound by ``maxMarketOrdersPerTurn`` for that commodity.

The tracker is deliberately stateless with respect to opponent action logs,
which are not part of the public state. All quantities are derived from
consecutive :class:`Observation` snapshots.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field
from typing import Any

from kaggriculture.env.constants import (
    ANIMALS,
    BUYABLE_PRODUCTS,
    CROPS,
    DEFAULT_CONFIG,
    PRICE_FLOOR,
    PRODUCTS,
    SHOPS,
    TOWN_CENTER_PRODUCTS,
)
from kaggriculture.env.observation import (
    Empty,
    Farm,
    Observation,
    Plant,
    Structure,
)


@dataclass(frozen=True, slots=True)
class CommodityEstimate:
    """Best estimate and interval for a single commodity."""

    estimate: float
    lower_bound: int
    upper_bound: int
    uncertainty_width: int
    floor_risk: float

    def __post_init__(self) -> None:
        if self.lower_bound < 0:
            raise ValueError(f"lower_bound must be >= 0, got {self.lower_bound}")
        if self.upper_bound < self.lower_bound:
            raise ValueError(f"upper_bound {self.upper_bound} < lower_bound {self.lower_bound}")
        if self.uncertainty_width != self.upper_bound - self.lower_bound:
            raise ValueError("uncertainty_width does not match bounds")
        if not 0.0 <= self.floor_risk <= 1.0:
            raise ValueError(f"floor_risk must be in [0, 1], got {self.floor_risk}")


def town_consumption_between(
    prev_step: int,
    now_step: int,
    unlocked_shops: Iterable[str],
    *,
    shop_interval: int = 4,
    center_interval: int = 24,
) -> dict[str, int]:
    """Deterministic town consumption over the half-open range [prev_step, now_step).

    ``prev_step`` and ``now_step`` count how many steps have been processed at
    each snapshot, so a delta of 1 means one step (``prev_step``) was processed
    between them. ``unlocked_shops`` is the shop list active during that
    processed step; a new shop unlocked at end-of-day boundary within the step
    is not yet consuming, so the pre-boundary shop list is correct.
    """
    if now_step < prev_step:
        raise ValueError(f"now_step {now_step} < prev_step {prev_step}")
    out: dict[str, int] = dict.fromkeys(PRODUCTS, 0)
    shops = list(unlocked_shops)
    for step in range(prev_step, now_step):
        if step % shop_interval == 0:
            for shop in shops:
                products = SHOPS[shop]
                multiplier = 2 if len(products) == 1 else 1
                for item in products:
                    out[item] += multiplier
        if step % center_interval == 0:
            for item in TOWN_CENTER_PRODUCTS:
                out[item] += 1
    return out


def _step_of(obs: Observation, turns_per_day: int) -> int:
    """Monotonic step index derived from (day, hour).

    ``obs.day`` and ``obs.hour`` are set post-processing to describe the *next*
    step to be processed, so ``day * turns_per_day + hour`` is exactly the count
    of steps already processed to reach this snapshot.
    """
    return obs.day * turns_per_day + obs.hour


def _hand_totals(obs: Observation) -> dict[str, int]:
    total: dict[str, int] = dict.fromkeys(PRODUCTS, 0)
    for inv in obs.private.inventories:
        for item, n in inv.items():
            if item in total:
                total[item] += n
    return total


def _harvest_from_farm(prev: Farm, now: Farm) -> dict[str, int]:
    """Approximate this turn's harvest per product on ``farm``.

    Harvest sets ``yield_units`` to zero atomically (see ``_apply_unit_action``
    HARVEST branch), so the only signal is a drop from ``yield_units > 0`` on
    ``prev`` to ``yield_units == 0`` on ``now``. Two transitions match this:

    - Non-ongoing plant harvested: tile turns from Plant to Empty.
    - Ongoing plant or animal harvested: tile persists with yield reset to 0.

    Partial ``yield_units`` drops on a persisting tile are natural decay past
    ``max_lifespan_step`` and are not attributed to harvest. Weed transitions
    also do not count: the yield is lost, not collected.
    """
    out: dict[str, int] = dict.fromkeys(PRODUCTS, 0)
    for prev_row, now_row in zip(prev.tiles, now.tiles, strict=True):
        for p, n in zip(prev_row, now_row, strict=True):
            if isinstance(p, Plant):
                if isinstance(n, Plant) and n.planted_day == p.planted_day and n.crop == p.crop:
                    if p.yield_units > 0 and n.yield_units == 0:
                        out[p.crop] += p.yield_units
                elif isinstance(n, Empty) and p.yield_units > 0 and not CROPS[p.crop]["ongoing"]:
                    out[p.crop] += p.yield_units
            elif (
                isinstance(p, Structure)
                and p.animal is not None
                and isinstance(n, Structure)
                and n.animal == p.animal
                and n.placed_day == p.placed_day
                and p.yield_units > 0
                and n.yield_units == 0
            ):
                out[ANIMALS[p.animal]["product"]] += p.yield_units
    return out


def _wheat_fed_on_farm(prev: Farm, now: Farm, day_boundary: bool) -> int:
    """Count wheat units used to feed animals between two snapshots.

    Within a day, ``fed_today`` toggling ``False -> True`` on a persisting
    animal counts as one FEED. At a day boundary the end-of-day resets
    ``fed_today`` to False and sets ``consecutive_unfed`` to 0 iff the animal
    was fed that day; we count a boundary feed only if ``prev.fed_today`` was
    False and ``now.consecutive_unfed`` is 0.
    """
    fed = 0
    for prev_row, now_row in zip(prev.tiles, now.tiles, strict=True):
        for p, n in zip(prev_row, now_row, strict=True):
            if not (
                isinstance(p, Structure)
                and p.animal is not None
                and isinstance(n, Structure)
                and n.animal == p.animal
                and n.placed_day == p.placed_day
            ):
                continue
            if day_boundary:
                if not p.fed_today and n.consecutive_unfed == 0:
                    fed += 1
            else:
                if n.fed_today and not p.fed_today:
                    fed += 1
    return fed


def _fertilize_used_on_farm(prev: Farm, now: Farm) -> int:
    """Count FERTILIZER used on plants between two snapshots.

    A FERTILIZE action raises ``fertilized_until_day`` on a plant tile. Any
    increase counts as one unit of fertilizer consumed. Multiple stacks on the
    same tile the same turn are not distinguishable and count as one; the
    simulator's FERTILIZE also caps to ``max(prev, day + 2)`` per call.
    """
    used = 0
    for prev_row, now_row in zip(prev.tiles, now.tiles, strict=True):
        for p, n in zip(prev_row, now_row, strict=True):
            if not (
                isinstance(p, Plant)
                and isinstance(n, Plant)
                and n.planted_day == p.planted_day
                and n.crop == p.crop
            ):
                continue
            if n.fertilized_until_day > p.fertilized_until_day:
                used += 1
    return used


def _fertilizer_collected_on_farm(prev: Farm, now: Farm) -> int:
    """Count COLLECT_FERTILIZER units gained between two snapshots.

    ``fertilizer_available`` toggling ``True -> False`` on a persisting animal
    tile within a day is one collect. At a day boundary the end-of-day sets
    ``fertilizer_available`` back to True, so a boundary transition True->True
    hides the collection. We approximate by only counting within-day drops.
    """
    collected = 0
    for prev_row, now_row in zip(prev.tiles, now.tiles, strict=True):
        for p, n in zip(prev_row, now_row, strict=True):
            if not (
                isinstance(p, Structure)
                and p.animal is not None
                and isinstance(n, Structure)
                and n.animal == p.animal
                and n.placed_day == p.placed_day
            ):
                continue
            if p.fertilizer_available and not n.fertilizer_available:
                collected += 1
    return collected


@dataclass
class OpponentInventoryTracker:
    """Stateful estimator of the opponent's per-commodity holdings.

    Feed each turn's observation to :meth:`update`. The returned dict maps
    every product in :data:`PRODUCTS` to a :class:`CommodityEstimate`.

    ``max_orders_per_turn`` bounds how many units the opponent can move per
    turn via the market queue, which caps the widening of the uncertainty
    interval when floor sales are possible. Defaults to the value from
    :data:`DEFAULT_CONFIG`.
    ``shed_capacity`` is the hard ceiling on any single commodity's estimate.
    """

    max_orders_per_turn: int = int(DEFAULT_CONFIG["maxMarketOrdersPerTurn"])
    shed_capacity: int = int(DEFAULT_CONFIG["shedCapacity"])
    turns_per_day: int = int(DEFAULT_CONFIG["turnsPerDay"])
    shop_interval: int = int(DEFAULT_CONFIG["townShopSellInterval"])
    center_interval: int = int(DEFAULT_CONFIG["townCenterSellInterval"])

    _prev_obs: Observation | None = field(default=None, init=False)
    _estimate: dict[str, float] = field(init=False)
    _slack: dict[str, int] = field(init=False)

    def __post_init__(self) -> None:
        if self.max_orders_per_turn <= 0:
            raise ValueError("max_orders_per_turn must be positive")
        if self.shed_capacity <= 0:
            raise ValueError("shed_capacity must be positive")
        self._estimate = dict.fromkeys(PRODUCTS, 0.0)
        self._slack = dict.fromkeys(PRODUCTS, 0)

    @property
    def estimates(self) -> dict[str, CommodityEstimate]:
        return self._build_estimates(prices=None)

    def _build_estimates(self, prices: dict[str, int] | None) -> dict[str, CommodityEstimate]:
        out: dict[str, CommodityEstimate] = {}
        for item in PRODUCTS:
            est = max(0.0, min(float(self.shed_capacity), self._estimate[item]))
            slack = self._slack[item]
            upper = int(min(self.shed_capacity, round(est) + slack))
            lower = int(max(0, round(est) - slack))
            floor_risk = 0.0
            if prices is not None and prices.get(item, 0) <= PRICE_FLOOR:
                floor_risk = 1.0
            out[item] = CommodityEstimate(
                estimate=est,
                lower_bound=lower,
                upper_bound=upper,
                uncertainty_width=upper - lower,
                floor_risk=floor_risk,
            )
        return out

    def update(self, obs: Observation) -> dict[str, CommodityEstimate]:
        """Advance the tracker by one turn and return the current estimates."""
        prices = obs.market.prices
        if self._prev_obs is None:
            self._prev_obs = obs
            return self._build_estimates(prices=prices)

        prev = self._prev_obs
        prev_step = _step_of(prev, self.turns_per_day)
        now_step = _step_of(obs, self.turns_per_day)
        if now_step <= prev_step:
            self._prev_obs = obs
            return self._build_estimates(prices=prices)

        me_prev = prev.farms[obs.player]
        me_now = obs.farms[obs.player]
        opp_prev = prev.farms[1 - obs.player]
        opp_now = obs.farms[1 - obs.player]

        own_harvest = _harvest_from_farm(me_prev, me_now)
        opp_harvest = _harvest_from_farm(opp_prev, opp_now)

        boundary = obs.day > prev.day
        own_feed = _wheat_fed_on_farm(me_prev, me_now, day_boundary=boundary)
        opp_feed = _wheat_fed_on_farm(opp_prev, opp_now, day_boundary=boundary)

        own_fert_used = _fertilize_used_on_farm(me_prev, me_now)
        opp_fert_used = _fertilize_used_on_farm(opp_prev, opp_now)
        own_fert_collected = _fertilizer_collected_on_farm(me_prev, me_now)
        opp_fert_collected = _fertilizer_collected_on_farm(opp_prev, opp_now)

        own_shed_prev = {k: prev.private.shed.get(k, 0) for k in PRODUCTS}
        own_shed_now = {k: obs.private.shed.get(k, 0) for k in PRODUCTS}
        own_hand_prev = _hand_totals(prev)
        own_hand_now = _hand_totals(obs)

        town = town_consumption_between(
            prev_step,
            now_step,
            prev.town.unlocked_shops,
            shop_interval=self.shop_interval,
            center_interval=self.center_interval,
        )

        for item in PRODUCTS:
            own_holdings_delta = (
                own_shed_now[item] - own_shed_prev[item] + own_hand_now[item] - own_hand_prev[item]
            )
            own_produced = own_harvest[item]
            own_consumed = 0
            if item == "WHEAT":
                own_consumed += own_feed
            if item == "FERTILIZER":
                own_produced += own_fert_collected
                own_consumed += own_fert_used
            own_market_net_out = own_produced - own_consumed - own_holdings_delta

            market_delta = obs.market.inventory[item] - prev.market.inventory[item]
            opp_market_net_out = market_delta + town[item] - own_market_net_out

            if item not in BUYABLE_PRODUCTS and opp_market_net_out < 0:
                # Non-buyable: opp cannot buy this item; a negative flow means
                # our accounting undershot somewhere. Clamp and widen slack.
                self._slack[item] += -opp_market_net_out
                opp_market_net_out = 0

            opp_produced = opp_harvest[item]
            opp_consumed = 0
            if item == "WHEAT":
                opp_consumed += opp_feed
            if item == "FERTILIZER":
                opp_produced += opp_fert_collected
                opp_consumed += opp_fert_used

            self._estimate[item] += opp_produced - opp_consumed - opp_market_net_out

            if prices.get(item, 0) <= PRICE_FLOOR:
                self._slack[item] = min(
                    self._slack[item] + self.max_orders_per_turn,
                    self.shed_capacity,
                )

        self._prev_obs = obs
        return self._build_estimates(prices=prices)

    @classmethod
    def from_raw(
        cls, raw: dict[str, Any], player: int
    ) -> tuple[OpponentInventoryTracker, Observation]:
        """Convenience constructor for callers holding a raw obs dict."""
        raw = {**raw, "player": player}
        obs = Observation.from_dict(raw)
        tracker = cls()
        tracker.update(obs)
        return tracker, obs
