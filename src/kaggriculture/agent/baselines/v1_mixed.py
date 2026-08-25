"""Baseline v1: wheat and carrot on two adjacent tiles.

Farmer manages two tiles in the NW quadrant: CARROT on the starting tile
(4, 4), WHEAT one step west at (3, 4). Priorities per tile: water if a plant
is unwatered, harvest at the unfertilized cap, replant if empty and a seed is
in stock. Farmer moves toward whichever tile needs attention.

Adds crop variety and multi-tile management on top of v0. Still no animals,
no market awareness, no hires, no land expansion.
"""

from __future__ import annotations

from typing import Any

# Per-crop parameters used by this baseline (subset of CROPS constants,
# duplicated here so this file is self-contained for Kaggle-style loading).
_CROP_TABLE = {
    "WHEAT": {"seed": 10, "first_yield_day": 2, "max_yield_day": 4, "max_yield_no_fert": 4},
    "CARROT": {"seed": 20, "first_yield_day": 2, "max_yield_day": 3, "max_yield_no_fert": 3},
}

_HOME_TILE = (4, 4)  # CARROT
_SECOND_TILE = (3, 4)  # WHEAT
_TILES = [(_HOME_TILE, "CARROT"), (_SECOND_TILE, "WHEAT")]
_TURNS_PER_DAY = 24


def _needed_op(tile: Any, crop: str, day: int, hour: int, seeds_in_stock: int) -> str | None:
    """Return the op that this tile most needs, or None if it wants nothing."""
    spec = _CROP_TABLE[crop]
    if isinstance(tile, dict) and tile.get("kind") == "PLANT" and tile.get("crop") == crop:
        if not tile.get("watered_today"):
            return "WATER"
        age = day - int(tile["planted_day"])
        yield_units = int(tile.get("yield_units", 0))
        if yield_units >= spec["max_yield_no_fert"] and age >= spec["first_yield_day"]:
            return "HARVEST"
        return None
    if tile is None and seeds_in_stock > 0 and hour < _TURNS_PER_DAY - 1:
        return "PLANT"
    return None


def _step_towards(fx: int, fy: int, tx: int, ty: int) -> list[Any]:
    if fx == tx and fy == ty:
        return ["PASS"]
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
    day = int(obs.get("day", 0))
    hour = int(obs.get("hour", 0))
    seeds = private.get("seeds", {}) or {}
    shed = private.get("shed", {}) or {}
    money = float(me.get("money", 0.0))

    # Market: keep at least one seed of each crop and dump all shed produce.
    market: list[list[Any]] = []
    for crop, spec in _CROP_TABLE.items():
        if seeds.get(crop, 0) == 0 and money >= spec["seed"]:
            market.append(["BUY_SEED", crop, 1])
    for product in ("WHEAT", "CARROT"):
        n = int(shed.get(product, 0))
        if n > 0:
            market.append(["SELL", product, n])

    # Find the tile that needs attention, preferring the current position.
    farmer: list[Any] = ["PASS"]
    here_first = sorted(
        _TILES,
        key=lambda item: 0 if item[0] == (fx, fy) else 1,
    )
    for (tx, ty), crop in here_first:
        tile = me["tiles"][ty][tx]
        op = _needed_op(tile, crop, day, hour, seeds.get(crop, 0))
        if op is None:
            continue
        if (fx, fy) == (tx, ty):
            farmer = [op] if op != "PLANT" else ["PLANT", crop]
        else:
            farmer = _step_towards(fx, fy, tx, ty)
        break

    return {"farmer": farmer, "hands": [], "market": market}
