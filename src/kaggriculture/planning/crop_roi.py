"""Per-crop ROI model.

Given a crop and market conditions, produce expected coins per tile per day
and the full lifecycle profile (peak units, days to peak, gross and net
revenue). Derived analytically from the yield rules in
`kaggle_environments.envs.kaggriculture`:

- One-time crops (wheat, carrot, melon) grow one yield unit per watered day
  during a bonus window `[ceil(max_yield_day / 2), max_yield_day]`, capped at
  `max_yield`. Fertilizer during that window adds a second unit per day.
- Ongoing crops (tomato, strawberry) fire scheduled productions of 1 unit
  starting `first_yield_day`, every `interval` days, up to `max_yield`
  productions. Watering is required and fertilizer adds a second unit per
  production.

The formulas here match the numbers plotted in `notebooks/02-crop-yields.ipynb`
so the notebook and the module cannot drift.
"""

from __future__ import annotations

from dataclasses import dataclass

from kaggriculture.env.constants import CROPS, MARKET_PARAMS


@dataclass(frozen=True, slots=True)
class CropRoi:
    """Lifecycle ROI for one crop under a fixed care regime and market price."""

    crop: str
    watered: bool
    fertilized: bool
    price: float
    seed_cost: int
    fertilizer_cost: float
    lifecycle_units: int
    lifecycle_days: int
    gross_revenue: float
    net_revenue: float
    coins_per_tile_per_day: float


def one_time_yield_trace(
    crop: str, days: int, *, watered: bool = True, fertilized: bool = False
) -> list[int]:
    """Yield units on a one-time plant across `days` days under a care regime.

    Index `d` is the yield count at end of day `d` (day 0 is planting day).
    """
    spec = CROPS[crop]
    if spec["ongoing"]:
        raise ValueError(f"{crop} is an ongoing crop; use `ongoing_cumulative_trace`.")
    window_start = (spec["max_yield_day"] + 1) // 2
    max_day = spec["max_yield_day"]
    max_yield = spec["max_yield"]
    trace: list[int] = []
    y = 1
    for day in range(days + 1):
        if watered and window_start <= day <= max_day:
            bonus = 2 if fertilized else 1
            y = min(max_yield, y + bonus)
        if day > max_day + 1 and (day - max_day - 1) % 2 == 0:
            y = max(0, y - 1)
        trace.append(y)
    return trace


def ongoing_cumulative_trace(
    crop: str, days: int, *, watered: bool = True, fertilized: bool = False
) -> list[int]:
    """Cumulative units produced by an ongoing plant across `days` days."""
    spec = CROPS[crop]
    if not spec["ongoing"]:
        raise ValueError(f"{crop} is a one-time crop; use `one_time_yield_trace`.")
    first = spec["first_yield_day"]
    interval = spec["interval"]
    max_prod = spec["max_yield"]
    cum = 0
    prod_count = 0
    trace: list[int] = []
    for day in range(days + 1):
        since = day - first
        produce = watered and since >= 0 and since % interval == 0 and prod_count < max_prod
        if produce:
            cum += 2 if fertilized else 1
            prod_count += 1
        trace.append(cum)
    return trace


def lifecycle_units_and_days(
    crop: str, *, watered: bool = True, fertilized: bool = False
) -> tuple[int, int]:
    """Peak harvested units and the number of days to reach that peak.

    For one-time crops this is the yield on `max_yield_day`. For ongoing crops
    this is the total production after the last scheduled tick.
    """
    spec = CROPS[crop]
    if not spec["ongoing"]:
        trace = one_time_yield_trace(
            crop, spec["max_yield_day"], watered=watered, fertilized=fertilized
        )
        return trace[-1], spec["max_yield_day"]
    last_prod_day = spec["first_yield_day"] + (spec["max_yield"] - 1) * spec["interval"]
    trace = ongoing_cumulative_trace(crop, last_prod_day, watered=watered, fertilized=fertilized)
    return trace[-1], last_prod_day


def crop_roi(
    crop: str,
    *,
    watered: bool = True,
    fertilized: bool = False,
    price: float | None = None,
    seed_cost: int | None = None,
    fertilizer_cost: float = 0.0,
) -> CropRoi:
    """ROI for one crop under a care regime and market conditions.

    `price` defaults to the base sell price. `seed_cost` defaults to the spec
    seed cost. `fertilizer_cost` is the total fertilizer spend attributed to
    one lifecycle (0.0 by default so callers who source fertilizer from their
    own animals pay nothing; pass `MARKET_PARAMS['FERTILIZER']['base']` for a
    single market-bought application).
    """
    if crop not in CROPS:
        raise KeyError(crop)
    if price is None:
        price = float(MARKET_PARAMS[crop]["base"])
    if seed_cost is None:
        seed_cost = CROPS[crop]["seed"]
    if not fertilized and fertilizer_cost != 0.0:
        raise ValueError("fertilizer_cost is non-zero but fertilized is False.")

    units, days = lifecycle_units_and_days(crop, watered=watered, fertilized=fertilized)
    gross = units * price
    net = gross - seed_cost - fertilizer_cost
    per_day = net / max(1, days)
    return CropRoi(
        crop=crop,
        watered=watered,
        fertilized=fertilized,
        price=price,
        seed_cost=seed_cost,
        fertilizer_cost=fertilizer_cost,
        lifecycle_units=units,
        lifecycle_days=days,
        gross_revenue=gross,
        net_revenue=net,
        coins_per_tile_per_day=per_day,
    )


def crop_roi_table(
    *,
    watered: bool = True,
    fertilized: bool = False,
    price_map: dict[str, float] | None = None,
    fertilizer_cost: float = 0.0,
) -> list[CropRoi]:
    """ROI for every crop under a fixed care regime.

    `price_map` overrides the default base price per crop. Missing keys fall
    back to the base price.
    """
    rows: list[CropRoi] = []
    for crop in CROPS:
        price = None if price_map is None else price_map.get(crop)
        rows.append(
            crop_roi(
                crop,
                watered=watered,
                fertilized=fertilized,
                price=price,
                fertilizer_cost=fertilizer_cost,
            )
        )
    return rows
