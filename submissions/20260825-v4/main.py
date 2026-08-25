"""Kaggriculture submission - agent v4 (2026-08-25).

Baseline v4 from `src/kaggriculture/agent/baselines/v4_expansion.py` copied
verbatim so Kaggle's runner can exec this single file.

Strategy summary: farmer manages one wheat tile (3, 4) and two carrot tiles
((4, 4) and (3, 3)), plus one goose in a coop at (4, 3). Hired hand primarily
tends the second carrot tile. Fertilizer produced by the goose is applied to
crops at the start of their bonus window. Market-responsive selling holds
produce below base price and force-sells on the last day.

Internal Elo ladder (round-robin over baselines + built-ins): v4 3165, v3 2590,
v2 2105, v1 1659, v0 1234, starter 819, pass 409, random 19.
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
_WHEAT_A = (3, 4)
_COOP_TILE = (4, 3)
_CARROT_B = (3, 3)
_SHED_ACCESS = {(4, 4), (5, 4), (4, 5), (5, 5)}
_TURNS_PER_DAY = 24
_GOOSE_PRICE = 300
_LAND_NE_PRICE = 1000
_MONEY_BUFFER_FOR_LAND = 1400

_SELL_MIN_PRICE = {"WHEAT": 25, "CARROT": 35, "EGG": 50, "FERTILIZER": 90}
_WHEAT_STOCKPILE_BUY_PRICE = 20
_WHEAT_STOCKPILE_CAP = 10
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


def _hand_op(
    hx: int,
    hy: int,
    tiles: list[list[Any]],
    unlocked: set[str],
    day: int,
    hour: int,
    seeds: dict[str, int],
) -> list[Any]:
    primary: list[tuple[tuple[int, int], str]] = [(_CARROT_B, "CARROT")]
    fallback: list[tuple[tuple[int, int], str]] = [(_HOME, "CARROT"), (_WHEAT_A, "WHEAT")]
    _ = unlocked
    for tiles_group in (primary, fallback):
        for (tx, ty), _crop in tiles_group:
            tile = tiles[ty][tx]
            if (
                isinstance(tile, dict)
                and tile.get("kind") == "PLANT"
                and not tile.get("watered_today")
            ):
                if (hx, hy) == (tx, ty):
                    return ["WATER"]
                return _step_towards(hx, hy, tx, ty)
        for (tx, ty), crop in tiles_group:
            tile = tiles[ty][tx]
            if not (
                isinstance(tile, dict) and tile.get("kind") == "PLANT" and tile.get("crop") == crop
            ):
                continue
            spec = _CROP_TABLE[crop]
            plant_fertilized = int(tile.get("fertilized_until_day", -1)) >= day
            cap = spec["max_yield_fert"] if plant_fertilized else spec["max_yield_no_fert"]
            age = day - int(tile.get("planted_day", day))
            if int(tile.get("yield_units", 0)) >= cap and age >= spec["first_yield_day"]:
                if (hx, hy) == (tx, ty):
                    return ["HARVEST"]
                return _step_towards(hx, hy, tx, ty)
        for (tx, ty), crop in tiles_group:
            tile = tiles[ty][tx]
            if tile is None and seeds.get(crop, 0) > 0 and hour < _TURNS_PER_DAY - 1:
                if (hx, hy) == (tx, ty):
                    return ["PLANT", crop]
                return _step_towards(hx, hy, tx, ty)
    return ["PASS"]


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
    hands_positions = [tuple(p) for p in me.get("hands", [])]
    unlocked = set(me.get("unlocked_quadrants", ["NW"]))
    hires_today = int(me.get("hires_today", 0))

    coop_tile = tiles[_COOP_TILE[1]][_COOP_TILE[0]]
    wheat_a = tiles[_WHEAT_A[1]][_WHEAT_A[0]]

    coop_built = isinstance(coop_tile, dict) and coop_tile.get("kind") == "COOP"
    goose_placed = coop_built and coop_tile.get("animal") == "GOOSE"
    goose_bought = int(shed.get("GOOSE", 0)) + int(farmer_inv.get("GOOSE", 0)) > 0 or goose_placed

    total_wheat_on_hand = int(shed.get("WHEAT", 0)) + int(farmer_inv.get("WHEAT", 0))
    wheat_reserve = 2 if goose_placed else 0

    wheat_plant_ready = (
        isinstance(wheat_a, dict)
        and wheat_a.get("kind") == "PLANT"
        and day - int(wheat_a.get("planted_day", day)) >= 2
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

    if day >= 3 and hires_today < 1 and money >= 10:
        market.append(["HIRE"])

    wheat_price = int(market_prices.get("WHEAT", 0))
    if (
        goose_placed
        and total_wheat_on_hand < _WHEAT_STOCKPILE_CAP
        and 0 < wheat_price <= _WHEAT_STOCKPILE_BUY_PRICE
        and money >= wheat_price
    ):
        market.append(["BUY_PRODUCT", "WHEAT", 1])
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

    def _resp(farmer_op: list[Any]) -> dict[str, Any]:
        hand_ops = [
            _hand_op(hx, hy, tiles, unlocked, day, hour, seeds) for hx, hy in hands_positions
        ]
        return {"farmer": farmer_op, "hands": hand_ops, "market": market}

    if int(shed.get("GOOSE", 0)) > 0 and int(farmer_inv.get("GOOSE", 0)) == 0:
        if (fx, fy) in _SHED_ACCESS:
            return _resp(["PICKUP", "GOOSE", 1])
        return _resp(_step_towards(fx, fy, *_HOME))

    if int(farmer_inv.get("GOOSE", 0)) > 0:
        if (fx, fy) == _COOP_TILE and coop_built and not goose_placed:
            return _resp(["PLACE", "GOOSE", 1])
        if (fx, fy) == _COOP_TILE and coop_tile is None:
            return _resp(["BUILD_COOP"])
        return _resp(_step_towards(fx, fy, *_COOP_TILE))

    if not coop_built and coop_tile is None:
        if (fx, fy) == _COOP_TILE:
            return _resp(["BUILD_COOP"])
        return _resp(_step_towards(fx, fy, *_COOP_TILE))

    if goose_placed:
        eggs_ready = int(coop_tile.get("yield_units", 0)) > 0
        needs_feed = not bool(coop_tile.get("fed_today", False))
        needs_care = not bool(coop_tile.get("cared_today", False))
        fert_available = bool(coop_tile.get("fertilizer_available", False))
        has_wheat = int(farmer_inv.get("WHEAT", 0)) > 0
        if (fx, fy) == _COOP_TILE:
            if eggs_ready:
                return _resp(["HARVEST"])
            if needs_feed and has_wheat:
                return _resp(["FEED"])
            if fert_available:
                return _resp(["COLLECT_FERTILIZER"])
            if needs_care and not needs_feed:
                return _resp(["CARE"])
        elif eggs_ready or fert_available or (needs_feed and has_wheat):
            return _resp(_step_towards(fx, fy, *_COOP_TILE))
        if needs_feed and not has_wheat and int(shed.get("WHEAT", 0)) > 0:
            if (fx, fy) in _SHED_ACCESS:
                return _resp(["PICKUP", "WHEAT", 1])
            return _resp(_step_towards(fx, fy, *_HOME))

    carrying_produce = any(farmer_inv.get(p, 0) > 0 for p in ("EGG", "CARROT"))
    if carrying_produce and (fx, fy) in _SHED_ACCESS:
        return _resp(["DROP"])

    crop_tiles: list[tuple[tuple[int, int], str]] = [
        (_WHEAT_A, "WHEAT"),
        (_HOME, "CARROT"),
        (_CARROT_B, "CARROT"),
    ]
    carrying_fert = int(farmer_inv.get("FERTILIZER", 0)) > 0
    for (tx, ty), crop in crop_tiles:
        tile = tiles[ty][tx]
        op = _crop_needed_op(tile, crop, day, hour, seeds.get(crop, 0), carrying_fert)
        if op is None:
            continue
        if (fx, fy) == (tx, ty):
            return _resp([op] if op != "PLANT" else ["PLANT", crop])
        return _resp(_step_towards(fx, fy, tx, ty))

    return _resp(["PASS"])
