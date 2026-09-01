"""Per-animal ROI model.

Steady-state coins per animal per day, net of the wheat feed cost, plus a
break-even day estimate for a fresh purchase. Matches the numbers plotted in
``notebooks/03-animal-economics.ipynb``.

Yield rules from the simulator:

- An animal starts producing on ``first_yield_day`` and produces one unit every
  ``interval`` days as long as it is fed the day of production.
- Feeding costs 1 wheat per animal per day. Skipping two consecutive days
  makes the animal escape (the coop / pasture stays).
- Care banks a pending yield on the day it is applied and pays it out at the
  next production tick. In steady state a cared-every-day animal produces
  ``1 + interval`` units per production, i.e. adds exactly one unit per day
  regardless of species.
"""

from __future__ import annotations

from dataclasses import dataclass

from kaggriculture.env.constants import ANIMALS, MARKET_PARAMS


@dataclass(frozen=True, slots=True)
class AnimalRoi:
    """Steady-state ROI for one animal under a fixed care regime and prices."""

    animal: str
    cared: bool
    product: str
    product_price: float
    feed_cost_per_day: float
    buy_cost: int
    first_yield_day: int
    interval: int
    steady_units_per_day: float
    gross_per_day: float
    net_per_day: float
    days_to_breakeven: float | None


def cumulative_net_trace(
    animal: str,
    days: int,
    *,
    cared: bool = False,
    product_price: float | None = None,
    feed_cost_per_day: float = 25.0,
) -> list[float]:
    """Cumulative net coins across `days` days for one fresh animal.

    Day 0 is the purchase day (capex paid, no feed). Feed is paid every
    subsequent day. Production ticks fire on days
    ``first_yield_day + k * interval`` for k >= 0.
    """
    if animal not in ANIMALS:
        raise KeyError(animal)
    spec = ANIMALS[animal]
    if product_price is None:
        product_price = float(MARKET_PARAMS[spec["product"]]["base"])
    cum = -float(spec["cost"])
    pending_care = 0
    trace: list[float] = []
    for day in range(days + 1):
        since_first = day - spec["first_yield_day"]
        producing = since_first >= 0 and since_first % spec["interval"] == 0
        if producing:
            units = 1 + pending_care
            cum += units * product_price
            pending_care = 0
        if day > 0:
            cum -= feed_cost_per_day
        if cared:
            pending_care += 1
        trace.append(cum)
    return trace


def _breakeven_day(
    animal: str,
    *,
    cared: bool,
    product_price: float,
    feed_cost_per_day: float,
    horizon: int,
) -> float | None:
    """First day the discrete cumulative-net trace hits zero, or None."""
    trace = cumulative_net_trace(
        animal,
        horizon,
        cared=cared,
        product_price=product_price,
        feed_cost_per_day=feed_cost_per_day,
    )
    for day, value in enumerate(trace):
        if value >= 0:
            return float(day)
    return None


def animal_roi(
    animal: str,
    *,
    cared: bool = False,
    product_price: float | None = None,
    feed_cost_per_day: float = 25.0,
    buy_cost: int | None = None,
) -> AnimalRoi:
    """ROI for one animal in steady state, net of wheat feed."""
    if animal not in ANIMALS:
        raise KeyError(animal)
    spec = ANIMALS[animal]
    product = spec["product"]
    if product_price is None:
        product_price = float(MARKET_PARAMS[product]["base"])
    if buy_cost is None:
        buy_cost = spec["cost"]

    interval = spec["interval"]
    units_per_prod = 1 + (interval if cared else 0)
    steady_units_per_day = units_per_prod / interval
    gross_per_day = steady_units_per_day * product_price
    net_per_day = gross_per_day - feed_cost_per_day
    breakeven = _breakeven_day(
        animal,
        cared=cared,
        product_price=product_price,
        feed_cost_per_day=feed_cost_per_day,
        horizon=30,
    )

    return AnimalRoi(
        animal=animal,
        cared=cared,
        product=product,
        product_price=product_price,
        feed_cost_per_day=feed_cost_per_day,
        buy_cost=buy_cost,
        first_yield_day=spec["first_yield_day"],
        interval=interval,
        steady_units_per_day=steady_units_per_day,
        gross_per_day=gross_per_day,
        net_per_day=net_per_day,
        days_to_breakeven=breakeven,
    )


def animal_roi_table(
    *,
    cared: bool = False,
    price_map: dict[str, float] | None = None,
    feed_cost_per_day: float = 25.0,
) -> list[AnimalRoi]:
    """ROI for every animal under a fixed care regime.

    `price_map` is keyed by product (EGG, MILK, WOOL). Missing keys fall back
    to the base price.
    """
    rows: list[AnimalRoi] = []
    for animal, spec in ANIMALS.items():
        price = None if price_map is None else price_map.get(spec["product"])
        rows.append(
            animal_roi(
                animal,
                cared=cared,
                product_price=price,
                feed_cost_per_day=feed_cost_per_day,
            )
        )
    return rows
