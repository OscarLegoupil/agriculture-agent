"""Baseline v2: v1 plus a goose coop.

Adds one goose in a coop on (4, 3), fed daily from wheat produced on (3, 4).
Setup takes ~5 days (buy goose $300, build coop, place goose, first egg day 4);
steady state is ~$50/day in eggs on top of v1's crop revenue.

Setup phases (once):
  1. Buy goose (into shed), build coop on (4, 3).
  2. Pick goose up from shed (at shed-access tile), place on the coop.
Ongoing:
  3. Water/harvest wheat on (3, 4); harvested wheat goes into farmer inventory.
  4. Water/harvest carrot on (4, 4).
  5. Feed goose 1 wheat/day; harvest eggs when yield_units > 0; drop eggs to shed.
Every turn the market queue tops up seeds, tops up the goose (once), and sells
shed produce.
"""

from __future__ import annotations

from typing import Any

# Duplicated so the file is self-contained for Kaggle-style loading.
_CROP_TABLE = {
    "WHEAT": {"seed": 10, "first_yield_day": 2, "max_yield_day": 4, "max_yield_no_fert": 4},
    "CARROT": {"seed": 20, "first_yield_day": 2, "max_yield_day": 3, "max_yield_no_fert": 3},
}

_HOME = (4, 4)  # CARROT + shed-access
_WHEAT_TILE = (3, 4)  # WHEAT
_COOP_TILE = (4, 3)  # COOP / goose
_SHED_ACCESS = {(4, 4), (5, 4), (4, 5), (5, 5)}
_TURNS_PER_DAY = 24
_GOOSE_PRICE = 300


def _crop_needed_op(tile: Any, crop: str, day: int, hour: int, seeds: int) -> str | None:
    spec = _CROP_TABLE[crop]
    if isinstance(tile, dict) and tile.get("kind") == "PLANT" and tile.get("crop") == crop:
        if not tile.get("watered_today"):
            return "WATER"
        age = day - int(tile["planted_day"])
        yield_units = int(tile.get("yield_units", 0))
        if yield_units >= spec["max_yield_no_fert"] and age >= spec["first_yield_day"]:
            return "HARVEST"
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

    coop_tile = tiles[_COOP_TILE[1]][_COOP_TILE[0]]
    wheat_tile = tiles[_WHEAT_TILE[1]][_WHEAT_TILE[0]]

    coop_built = isinstance(coop_tile, dict) and coop_tile.get("kind") == "COOP"
    goose_placed = coop_built and coop_tile.get("animal") == "GOOSE"
    goose_bought = int(shed.get("GOOSE", 0)) + int(farmer_inv.get("GOOSE", 0)) > 0 or goose_placed

    total_wheat_on_hand = int(shed.get("WHEAT", 0)) + int(farmer_inv.get("WHEAT", 0))
    wheat_reserve = 2 if goose_placed else 0

    # Only buy the goose once the wheat pipeline is in flight, so it does not
    # starve during setup.
    wheat_plant_ready = (
        isinstance(wheat_tile, dict)
        and wheat_tile.get("kind") == "PLANT"
        and day - int(wheat_tile.get("planted_day", day)) >= 2
    )
    wheat_pipeline_ready = wheat_plant_ready or total_wheat_on_hand >= 2

    # Market: buy seeds, buy one goose (only if none exists yet), and sell shed produce.
    market: list[list[Any]] = []
    for crop, spec in _CROP_TABLE.items():
        if seeds.get(crop, 0) == 0 and money >= spec["seed"]:
            market.append(["BUY_SEED", crop, 1])
    if not goose_bought and wheat_pipeline_ready and money >= _GOOSE_PRICE:
        market.append(["BUY_ANIMAL", "GOOSE", 1])
    # Emergency wheat top-up if the goose is about to starve.
    if goose_placed and total_wheat_on_hand == 0:
        market.append(["BUY_PRODUCT", "WHEAT", 1])
    wheat_in_shed = int(shed.get("WHEAT", 0))
    if wheat_in_shed > wheat_reserve:
        market.append(["SELL", "WHEAT", wheat_in_shed - wheat_reserve])
    for product in ("CARROT", "EGG"):
        n = int(shed.get(product, 0))
        if n > 0:
            market.append(["SELL", product, n])

    # ------------------------------------------------------------------
    # Farmer decision tree
    # ------------------------------------------------------------------

    # 0. Goose in shed but not carried: pick up at shed-adjacent tile.
    if int(shed.get("GOOSE", 0)) > 0 and not int(farmer_inv.get("GOOSE", 0)):
        if (fx, fy) in _SHED_ACCESS:
            return {"farmer": ["PICKUP", "GOOSE", 1], "hands": [], "market": market}
        return {"farmer": _step_towards(fx, fy, *_HOME), "hands": [], "market": market}

    # 1. If we carry a goose, walk to the coop tile and place it.
    if int(farmer_inv.get("GOOSE", 0)) > 0:
        if (fx, fy) == _COOP_TILE and coop_built and not goose_placed:
            return {"farmer": ["PLACE", "GOOSE", 1], "hands": [], "market": market}
        # Ensure coop exists first; walk there and build if empty.
        if (fx, fy) == _COOP_TILE and coop_tile is None:
            return {"farmer": ["BUILD_COOP"], "hands": [], "market": market}
        return {"farmer": _step_towards(fx, fy, *_COOP_TILE), "hands": [], "market": market}

    # 2. If no coop built yet and no goose in hand, coop first (needs empty tile).
    if not coop_built and coop_tile is None:
        if (fx, fy) == _COOP_TILE:
            return {"farmer": ["BUILD_COOP"], "hands": [], "market": market}
        return {"farmer": _step_towards(fx, fy, *_COOP_TILE), "hands": [], "market": market}

    # 3. Goose care: feed if unfed, harvest eggs, care if not cared.
    if goose_placed:
        eggs_ready = int(coop_tile.get("yield_units", 0)) > 0
        needs_feed = not bool(coop_tile.get("fed_today", False))
        needs_care = not bool(coop_tile.get("cared_today", False))
        has_wheat = int(farmer_inv.get("WHEAT", 0)) > 0
        if (fx, fy) == _COOP_TILE:
            if eggs_ready:
                return {"farmer": ["HARVEST"], "hands": [], "market": market}
            if needs_feed and has_wheat:
                return {"farmer": ["FEED"], "hands": [], "market": market}
            if needs_care and not needs_feed:
                # CARE only banks bonus for a fed-and-cared day; do it after feeding.
                return {"farmer": ["CARE"], "hands": [], "market": market}
        elif eggs_ready or (needs_feed and has_wheat):
            return {"farmer": _step_towards(fx, fy, *_COOP_TILE), "hands": [], "market": market}
        # Need wheat but do not have it: pick from shed if any.
        if needs_feed and not has_wheat and int(shed.get("WHEAT", 0)) > 0:
            if (fx, fy) in _SHED_ACCESS:
                return {"farmer": ["PICKUP", "WHEAT", 1], "hands": [], "market": market}
            return {"farmer": _step_towards(fx, fy, *_HOME), "hands": [], "market": market}

    # 4. Drop farmer produce (eggs / carrots) at the shed when possible.
    carrying_produce = any(farmer_inv.get(p, 0) > 0 for p in ("EGG", "CARROT"))
    if carrying_produce and (fx, fy) in _SHED_ACCESS:
        return {"farmer": ["DROP"], "hands": [], "market": market}

    # 5. Crop maintenance: wheat first (feed pipeline), then carrot.
    for (tx, ty), crop in ((_WHEAT_TILE, "WHEAT"), (_HOME, "CARROT")):
        tile = tiles[ty][tx]
        op = _crop_needed_op(tile, crop, day, hour, seeds.get(crop, 0))
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
