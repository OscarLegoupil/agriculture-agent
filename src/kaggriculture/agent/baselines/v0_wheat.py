"""Baseline v0: pure wheat loop.

Simplest possible profitable strategy. Farmer stays on the starting tile,
plants wheat, waters until yield reaches the unfertilized cap (4 units), then
harvests. Every turn the market queue tops up seed inventory and sells any
wheat in the shed.

No hands, no animals, no market awareness, no land expansion, no movement.
The floor of the internal Elo ladder.
"""

from __future__ import annotations

from typing import Any

WHEAT_SEED_PRICE = 10
FIRST_YIELD_DAY = 2
MAX_YIELD_NO_FERT = 4  # wheat cap without fertilizer

_TURNS_PER_DAY = 24


def agent(obs: dict[str, Any]) -> dict[str, Any]:
    player = int(obs.get("player", 0))
    farms = obs.get("farms", [])
    private = obs.get("private", {}) or {}
    if not farms or player >= len(farms):
        return {"farmer": ["PASS"], "hands": [], "market": []}

    me = farms[player]
    fx, fy = me["farmer"]
    tile = me["tiles"][fy][fx]
    day = int(obs.get("day", 0))
    hour = int(obs.get("hour", 0))
    seeds = private.get("seeds", {}) or {}
    shed = private.get("shed", {}) or {}
    money = float(me.get("money", 0.0))

    market: list[list[Any]] = []
    if seeds.get("WHEAT", 0) == 0 and money >= WHEAT_SEED_PRICE:
        market.append(["BUY_SEED", "WHEAT", 1])
    wheat_in_shed = int(shed.get("WHEAT", 0))
    if wheat_in_shed > 0:
        market.append(["SELL", "WHEAT", wheat_in_shed])

    farmer: list[Any] = ["PASS"]
    if isinstance(tile, dict) and tile.get("kind") == "PLANT" and tile.get("crop") == "WHEAT":
        age = day - int(tile["planted_day"])
        yield_units = int(tile.get("yield_units", 0))
        watered = bool(tile.get("watered_today", False))
        if not watered:
            farmer = ["WATER"]
        elif yield_units >= MAX_YIELD_NO_FERT and age >= FIRST_YIELD_DAY:
            farmer = ["HARVEST"]
    elif tile is None and seeds.get("WHEAT", 0) > 0 and hour < _TURNS_PER_DAY - 1:
        # Skip the last hour of a day: freshly planted seeds must be watered
        # same-day or they weed out at end-of-day refresh.
        farmer = ["PLANT", "WHEAT"]

    return {"farmer": farmer, "hands": [], "market": market}
