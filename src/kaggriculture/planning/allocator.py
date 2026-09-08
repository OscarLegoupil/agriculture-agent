"""Static resource allocator.

Given a tile budget and a price forecast, pick a crop-and-animal mix that
maximizes expected coins over the remaining season. This is the small
integer program that connects the ROI tables into a single decision.

Structure of the problem:

- Tiles are the constrained resource. Each non-wheat crop occupies 1 tile
  and produces at ``coins_per_tile_per_day`` over the horizon. Each animal
  needs its own structure tile (COOP for goose, PASTURE for cow and sheep);
  ``max_held`` caps unharvested produce, not how many animals fit.
- Animals are valued on their product plus the fertilizer they make daily,
  which is a larger revenue line than the product itself for every species.
- Wheat tiles are reserved to feed the animal roster. Peak daily wheat
  demand divided by the per-tile wheat yield rate gives the number of
  wheat tiles required.
- Every non-wheat non-structure tile is filled with the crop that has the
  highest expected coins per tile per day at forecasted prices.

We enumerate every feasible animal roster (small: at most a few hundred
tuples) and pick the roster + fill-crop combination that maximises
expected revenue. This is exact for the assumptions above and stays well
under a millisecond per call, which is what the "static" in the name buys.
"""

from __future__ import annotations

from dataclasses import dataclass

from kaggriculture.env.constants import ANIMALS, MARKET_PARAMS
from kaggriculture.planning.animal_roi import cumulative_net_trace
from kaggriculture.planning.crop_roi import crop_roi
from kaggriculture.planning.feed_budget import AnimalPlan, feed_budget


@dataclass(frozen=True, slots=True)
class Allocation:
    """One allocation decision."""

    tiles: int
    horizon_days: int
    fill_crop: str | None
    fill_crop_tiles: int
    wheat_tiles: int
    animal_counts: dict[str, int]
    structure_tiles: int
    expected_revenue: float
    fill_crop_revenue: float
    wheat_revenue: float
    animal_revenue: float


def _structures_for(counts: dict[str, int]) -> int:
    """One coop or pasture per animal: a structure holds exactly one occupant."""
    return sum(n for n in counts.values() if n > 0)


def _iter_animal_rosters(max_per_species: dict[str, int]) -> list[dict[str, int]]:
    rosters: list[dict[str, int]] = []
    goose_cap = max_per_species.get("GOOSE", ANIMALS["GOOSE"]["max_held"])
    cow_cap = max_per_species.get("COW", ANIMALS["COW"]["max_held"])
    sheep_cap = max_per_species.get("SHEEP", ANIMALS["SHEEP"]["max_held"])
    for g in range(goose_cap + 1):
        for c in range(cow_cap + 1):
            for s in range(sheep_cap + 1):
                rosters.append({"GOOSE": g, "COW": c, "SHEEP": s})
    return rosters


def _fill_crop_choice(
    *,
    price_map: dict[str, float] | None,
    watered: bool,
    fertilized: bool,
) -> tuple[str, float]:
    """Pick the crop with the highest coins-per-tile-per-day at forecast prices.

    Wheat is excluded because it is allocated separately as feed reserve.
    """
    best_crop: str | None = None
    best_rate = float("-inf")
    for candidate in ("CARROT", "TOMATO", "STRAWBERRY", "MELON"):
        price = None if price_map is None else price_map.get(candidate)
        roi = crop_roi(candidate, watered=watered, fertilized=fertilized, price=price)
        if roi.coins_per_tile_per_day > best_rate:
            best_rate = roi.coins_per_tile_per_day
            best_crop = candidate
    assert best_crop is not None
    return best_crop, best_rate


def _animal_revenue(
    counts: dict[str, int],
    *,
    horizon_days: int,
    price_map: dict[str, float] | None,
    feed_cost_per_day: float,
) -> float:
    fertilizer_price = float(MARKET_PARAMS["FERTILIZER"]["base"])
    if price_map is not None:
        fertilizer_price = price_map.get("FERTILIZER", fertilizer_price)
    total = 0.0
    for animal, n in counts.items():
        if n <= 0:
            continue
        product_price = None
        if price_map is not None:
            product_price = price_map.get(ANIMALS[animal]["product"])
        trace = cumulative_net_trace(
            animal,
            horizon_days,
            cared=True,
            product_price=product_price,
            feed_cost_per_day=feed_cost_per_day,
            fertilizer_price=fertilizer_price,
        )
        total += trace[-1] * n
    return total


def allocate(
    *,
    tiles: int,
    horizon_days: int,
    price_map: dict[str, float] | None = None,
    watered: bool = True,
    fertilized: bool = False,
    feed_cost_per_day: float = 25.0,
    max_animals_per_species: dict[str, int] | None = None,
) -> Allocation:
    """Choose the tile allocation maximising expected coins over the horizon.

    `tiles` is the total tile budget (crop tiles + wheat tiles + structure
    tiles). `horizon_days` is the number of remaining season days. Prices in
    `price_map` are forecasts per resource; missing keys fall back to the
    base price.
    """
    if tiles < 0:
        raise ValueError(f"tiles must be >= 0, got {tiles}")
    if horizon_days < 1:
        raise ValueError(f"horizon_days must be >= 1, got {horizon_days}")

    caps = max_animals_per_species or {}
    fill_crop, fill_rate = _fill_crop_choice(
        price_map=price_map,
        watered=watered,
        fertilized=fertilized,
    )

    best: Allocation | None = None
    for counts in _iter_animal_rosters(caps):
        structures = _structures_for(counts)
        roster = [AnimalPlan(animal=a, purchase_day=0, count=n) for a, n in counts.items() if n > 0]
        grown = feed_budget(
            roster,
            season_days=horizon_days,
            wheat_watered=watered,
            wheat_fertilized=fertilized,
        )
        # Feed is either grown on reserved tiles or bought for cash. Charging
        # both would double-count it, so each option is costed and the cheaper
        # one wins: tiles are the scarce resource early, cash is later.
        for wheat_tiles, feed_cash in ((grown.tiles_needed, 0.0), (0, feed_cost_per_day)):
            used_before_fill = wheat_tiles + structures
            if used_before_fill > tiles:
                continue
            fill_tiles = tiles - used_before_fill

            fill_revenue = fill_tiles * fill_rate * horizon_days
            # Wheat produced beyond the feed reserve has zero market value in
            # this static model (it is a feed buffer, not a sale target).
            wheat_revenue = 0.0
            animal_revenue = _animal_revenue(
                counts,
                horizon_days=horizon_days,
                price_map=price_map,
                feed_cost_per_day=feed_cash,
            )
            total = fill_revenue + wheat_revenue + animal_revenue

            if best is None or total > best.expected_revenue:
                best = Allocation(
                    tiles=tiles,
                    horizon_days=horizon_days,
                    fill_crop=fill_crop if fill_tiles > 0 else None,
                    fill_crop_tiles=fill_tiles,
                    wheat_tiles=wheat_tiles,
                    animal_counts={k: v for k, v in counts.items() if v > 0},
                    structure_tiles=structures,
                    expected_revenue=total,
                    fill_crop_revenue=fill_revenue,
                    wheat_revenue=wheat_revenue,
                    animal_revenue=animal_revenue,
                )

    assert best is not None
    return best
