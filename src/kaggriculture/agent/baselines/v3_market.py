"""Baseline v3: v2 plus market-responsive selling, cheap wheat top-ups, fertilizer reuse.

Additions on top of v2:

1. Hold shed produce when the sell price is strictly below its base; force-sell
   on the last in-game day and when the shed is near cap.
2. Buy wheat from the market whenever price dips $5 or more below base and we
   have room, so the goose is fed without emergency-price top-ups.
3. Collect the goose's daily fertilizer, apply one to each plant at the start
   of its bonus window (age = window_start). Wheat cap goes 4 -> 6 and carrot
   3 -> 4, so per-tile-per-day revenue rises meaningfully at essentially zero
   cost since fertilizer is a free by-product.
4. Sell surplus fertilizer at the market.

Otherwise identical tile layout as v2.
"""

from __future__ import annotations

from typing import Any

_CROP_TABLE = {
    "WHEAT": {
        "seed": 10,
        "first_yield_day": 2,
        "max_yield_day": 4,
        "max_yield_no_fert": 4,
        "max_yield_fert": 6,
        "window_start": 2,
    },
    "CARROT": {
        "seed": 20,
        "first_yield_day": 2,
        "max_yield_day": 3,
        "max_yield_no_fert": 3,
        "max_yield_fert": 4,
        "window_start": 2,
    },
}

_HOME = (4, 4)
_WHEAT_TILE = (3, 4)
_COOP_TILE = (4, 3)
_SHED_ACCESS = {(4, 4), (5, 4), (4, 5), (5, 5)}
_TURNS_PER_DAY = 24
_GOOSE_PRICE = 300

# Sell only if the current market price is at least this level (bases: wheat 25,
# carrot 35, egg 50). Withhold otherwise; the season-end liquidation catches any
# leftover.
_SELL_MIN_PRICE = {
    "WHEAT": 25,
    "CARROT": 35,
    "EGG": 50,
    "FERTILIZER": 90,
}
_WHEAT_STOCKPILE_BUY_PRICE = 20  # base 25; buy at $5 or more below base.
_WHEAT_STOCKPILE_CAP = 10  # do not stockpile more than this from market buys.

_SHED_HIGH_WATER = 80
_SEASON_LAST_DAY = 29


def _crop_needed_op(
    tile: Any, crop: str, day: int, hour: int, seeds: int, carrying_fert: bool
) -> str | None:
    spec = _CROP_TABLE[crop]
    if isinstance(tile, dict) and tile.get("kind") == "PLANT" and tile.get("crop") == crop:
        if not tile.get("watered_today"):
            return "WATER"
        age = day - int(tile["planted_day"])
        yield_units = int(tile.get("yield_units", 0))
        plant_fertilized = int(tile.get("fertilized_until_day", -1)) >= day
        cap = spec["max_yield_fert"] if plant_fertilized else spec["max_yield_no_fert"]
        if yield_units >= cap and age >= spec["first_yield_day"]:
            return "HARVEST"
        # Fertilize once, at the start of the bonus window, only if we carry one.
        if carrying_fert and not plant_fertilized and age == spec["window_start"]:
            return "FERTILIZE"
        return None
    if tile is None and seeds > 0 and hour < _TURNS_PER_DAY - 1:
        return "PLANT"
    return None


def _step_towards(fx: int, fy: int, tx: int, ty: int) -> list[Any]:
    if fx < tx:
        return ["EAST"]
    if fx > tx:
        return ["WEST"]
    if fy < ty:
        return ["SOUTH"]
    return ["NORTH"]


def agent(obs: dict[str, Any]) -> dict[str, Any]:
    player = int(obs.get("player", 0))
    farms = obs.get("farms", [])
    private = obs.get("private", {}) or {}
    if not farms or player >= len(farms):
        return {"farmer": ["PASS"], "hands": [], "market": []}

    me = farms[player]
    fx, fy = me["farmer"]
    tiles = me["tiles"]
    day = int(obs.get("day", 0))
    hour = int(obs.get("hour", 0))
    seeds = private.get("seeds", {}) or {}
    shed = private.get("shed", {}) or {}
    inventories = private.get("inventories", [{}]) or [{}]
    farmer_inv = inventories[0] if inventories else {}
    money = float(me.get("money", 0.0))
    market_prices = (obs.get("market", {}) or {}).get("prices", {}) or {}

    coop_tile = tiles[_COOP_TILE[1]][_COOP_TILE[0]]
    wheat_tile = tiles[_WHEAT_TILE[1]][_WHEAT_TILE[0]]

    coop_built = isinstance(coop_tile, dict) and coop_tile.get("kind") == "COOP"
    goose_placed = coop_built and coop_tile.get("animal") == "GOOSE"
    goose_bought = int(shed.get("GOOSE", 0)) + int(farmer_inv.get("GOOSE", 0)) > 0 or goose_placed

    total_wheat_on_hand = int(shed.get("WHEAT", 0)) + int(farmer_inv.get("WHEAT", 0))
    wheat_reserve = 2 if goose_placed else 0

    wheat_plant_ready = (
        isinstance(wheat_tile, dict)
        and wheat_tile.get("kind") == "PLANT"
        and day - int(wheat_tile.get("planted_day", day)) >= 2
    )
    wheat_pipeline_ready = wheat_plant_ready or total_wheat_on_hand >= 2

    shed_load = sum(int(v) for v in shed.values())
    liquidate = day >= _SEASON_LAST_DAY or shed_load >= _SHED_HIGH_WATER

    market: list[list[Any]] = []
    for crop, spec in _CROP_TABLE.items():
        if seeds.get(crop, 0) == 0 and money >= spec["seed"]:
            market.append(["BUY_SEED", crop, 1])
    if not goose_bought and wheat_pipeline_ready and money >= _GOOSE_PRICE:
        market.append(["BUY_ANIMAL", "GOOSE", 1])

    # Cheap wheat stockpile when the market dips below _WHEAT_STOCKPILE_BUY_PRICE.
    wheat_price = int(market_prices.get("WHEAT", 0))
    if (
        goose_placed
        and total_wheat_on_hand < _WHEAT_STOCKPILE_CAP
        and wheat_price > 0
        and wheat_price <= _WHEAT_STOCKPILE_BUY_PRICE
        and money >= wheat_price
    ):
        market.append(["BUY_PRODUCT", "WHEAT", 1])
    # Emergency wheat: only if the goose has literally nothing.
    if goose_placed and total_wheat_on_hand == 0:
        market.append(["BUY_PRODUCT", "WHEAT", 1])

    wheat_in_shed = int(shed.get("WHEAT", 0))
    if wheat_in_shed > wheat_reserve and (liquidate or wheat_price >= _SELL_MIN_PRICE["WHEAT"]):
        market.append(["SELL", "WHEAT", wheat_in_shed - wheat_reserve])
    for product in ("CARROT", "EGG", "FERTILIZER"):
        n = int(shed.get(product, 0))
        if n <= 0:
            continue
        price = int(market_prices.get(product, 0))
        min_price = _SELL_MIN_PRICE.get(product, 1)
        if liquidate or price >= min_price:
            market.append(["SELL", product, n])

    if int(shed.get("GOOSE", 0)) > 0 and not int(farmer_inv.get("GOOSE", 0)):
        if (fx, fy) in _SHED_ACCESS:
            return {"farmer": ["PICKUP", "GOOSE", 1], "hands": [], "market": market}
        return {"farmer": _step_towards(fx, fy, *_HOME), "hands": [], "market": market}

    if int(farmer_inv.get("GOOSE", 0)) > 0:
        if (fx, fy) == _COOP_TILE and coop_built and not goose_placed:
            return {"farmer": ["PLACE", "GOOSE", 1], "hands": [], "market": market}
        if (fx, fy) == _COOP_TILE and coop_tile is None:
            return {"farmer": ["BUILD_COOP"], "hands": [], "market": market}
        return {"farmer": _step_towards(fx, fy, *_COOP_TILE), "hands": [], "market": market}

    if not coop_built and coop_tile is None:
        if (fx, fy) == _COOP_TILE:
            return {"farmer": ["BUILD_COOP"], "hands": [], "market": market}
        return {"farmer": _step_towards(fx, fy, *_COOP_TILE), "hands": [], "market": market}

    if goose_placed:
        eggs_ready = int(coop_tile.get("yield_units", 0)) > 0
        needs_feed = not bool(coop_tile.get("fed_today", False))
        needs_care = not bool(coop_tile.get("cared_today", False))
        fert_available = bool(coop_tile.get("fertilizer_available", False))
        has_wheat = int(farmer_inv.get("WHEAT", 0)) > 0
        if (fx, fy) == _COOP_TILE:
            if eggs_ready:
                return {"farmer": ["HARVEST"], "hands": [], "market": market}
            if needs_feed and has_wheat:
                return {"farmer": ["FEED"], "hands": [], "market": market}
            if fert_available:
                return {"farmer": ["COLLECT_FERTILIZER"], "hands": [], "market": market}
            if needs_care and not needs_feed:
                return {"farmer": ["CARE"], "hands": [], "market": market}
        elif eggs_ready or (needs_feed and has_wheat):
            return {"farmer": _step_towards(fx, fy, *_COOP_TILE), "hands": [], "market": market}
        if needs_feed and not has_wheat and int(shed.get("WHEAT", 0)) > 0:
            if (fx, fy) in _SHED_ACCESS:
                return {"farmer": ["PICKUP", "WHEAT", 1], "hands": [], "market": market}
            return {"farmer": _step_towards(fx, fy, *_HOME), "hands": [], "market": market}

    carrying_produce = any(farmer_inv.get(p, 0) > 0 for p in ("EGG", "CARROT"))
    if carrying_produce and (fx, fy) in _SHED_ACCESS:
        return {"farmer": ["DROP"], "hands": [], "market": market}

    for (tx, ty), crop in ((_WHEAT_TILE, "WHEAT"), (_HOME, "CARROT")):
        tile = tiles[ty][tx]
        carrying_fert = int(farmer_inv.get("FERTILIZER", 0)) > 0
        op = _crop_needed_op(tile, crop, day, hour, seeds.get(crop, 0), carrying_fert)
        if op is None:
            continue
        if (fx, fy) == (tx, ty):
            return {
                "farmer": [op] if op != "PLANT" else ["PLANT", crop],
                "hands": [],
                "market": market,
            }
        return {"farmer": _step_towards(fx, fy, tx, ty), "hands": [], "market": market}

    return {"farmer": ["PASS"], "hands": [], "market": market}
