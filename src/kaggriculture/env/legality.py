"""Action legality checker.

Best-effort static analysis of a proposed action against an observation. The
ground truth is what the simulator's interpreter accepts; this module catches
the mistakes that show up as silent no-ops in real episodes: missing seeds,
insufficient money, off-board moves, tile / adjacency mismatches, and the
atomic multi-unit PLANT rule (if total PLANT requests for a crop exceed the
seed count, the env drops ALL of them for that crop this turn).

Used by tests and by the eval harness to count wasted actions per episode.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal, TypeAlias

from kaggriculture.env.constants import (
    ANIMALS,
    BUYABLE_PRODUCTS,
    CROPS,
    LAND_ORDER,
    LAND_PRICES,
    PRODUCTS,
)
from kaggriculture.env.observation import (
    Empty,
    Locked,
    Observation,
    Plant,
    Structure,
    Weed,
)

Component: TypeAlias = Literal["farmer", "hands", "market"]

MOVES: dict[str, tuple[int, int]] = {
    "NORTH": (0, -1),
    "SOUTH": (0, 1),
    "EAST": (1, 0),
    "WEST": (-1, 0),
}


@dataclass(frozen=True, slots=True)
class Issue:
    component: Component
    index: int
    op: list[Any]
    reason: str


def _shed_access(board_size: int) -> set[tuple[int, int]]:
    half = board_size // 2
    return {(half - 1, half - 1), (half, half - 1), (half - 1, half), (half, half)}


def _is_shed_adjacent(pos: tuple[int, int], board_size: int) -> bool:
    return pos in _shed_access(board_size)


def _check_unit_op(
    obs: Observation,
    unit_index: int,
    op: list[Any],
    board_size: int,
) -> str | None:
    """Return a reason string if this unit op is illegal or a no-op, else None."""
    if not isinstance(op, list) or not op:
        return "empty or non-list op"
    kind = op[0]

    # Position for this unit (0 = main farmer, 1+ = hand at that index).
    me = obs.me
    if unit_index == 0:
        pos = me.farmer
    else:
        hand_idx = unit_index - 1
        if hand_idx >= len(me.hands):
            return f"no hand at index {hand_idx}"
        pos = me.hands[hand_idx]

    x, y = pos
    tile = me.tiles[y][x] if 0 <= y < board_size and 0 <= x < board_size else None
    inv = obs.private.inventories[unit_index] if unit_index < len(obs.private.inventories) else {}

    if kind in MOVES:
        dx, dy = MOVES[kind]
        nx, ny = x + dx, y + dy
        if not (0 <= nx < board_size and 0 <= ny < board_size):
            return f"move {kind} goes off-board from ({x},{y})"
        return None

    if kind == "PASS":
        return None

    # Shed operations resolve before the LOCKED guard (three of four shed-access
    # tiles start locked and the shed itself is always owned).
    if kind == "DROP":
        return (
            None if _is_shed_adjacent(pos, board_size) else "DROP requires standing shed-adjacent"
        )

    if kind == "PICKUP":
        if not _is_shed_adjacent(pos, board_size):
            return "PICKUP requires standing shed-adjacent"
        if len(op) < 2:
            return "PICKUP missing item argument"
        item = op[1]
        if obs.private.shed.get(item, 0) <= 0:
            return f"no {item} in shed"
        return None

    if kind == "PLACE":
        if len(op) < 2:
            return "PLACE missing item argument"
        item = op[1]
        if (
            item in ANIMALS
            and isinstance(tile, Structure)
            and tile.animal is None
            and tile.kind == ANIMALS[item]["structure"]
        ):
            if inv.get(item, 0) <= 0:
                return f"no {item} in inventory"
            return None
        if _is_shed_adjacent(pos, board_size):
            if inv.get(item, 0) <= 0:
                return f"no {item} in inventory to drop into shed"
            return None
        return f"PLACE {item} on non-matching tile and not shed-adjacent"

    # Everything below mutates the standing tile, so LOCKED / off-board no-ops.
    if isinstance(tile, Locked):
        return f"{kind} on locked tile"
    if tile is None:
        return f"{kind} on invalid tile position"

    if kind == "PLANT":
        if len(op) < 2:
            return "PLANT missing crop argument"
        crop = op[1]
        if crop not in CROPS:
            return f"unknown crop {crop!r}"
        if not isinstance(tile, Empty):
            return "PLANT on non-empty tile"
        if obs.private.seeds.get(crop, 0) <= 0:
            return f"no {crop} seeds"
        return None

    if kind == "WATER":
        if not isinstance(tile, Plant):
            return "WATER on non-plant tile"
        if tile.watered_today:
            return "already watered today (no-op)"
        return None

    if kind == "HARVEST":
        if not isinstance(tile, Plant | Structure):
            return "HARVEST on non-harvestable tile"
        if (
            isinstance(tile, Plant)
            and obs.day - tile.planted_day < CROPS[tile.crop]["first_yield_day"]
        ):
            return "HARVEST before first_yield_day"
        if tile.yield_units <= 0:
            return "HARVEST with no units available"
        return None

    if kind == "FERTILIZE":
        if not isinstance(tile, Plant):
            return "FERTILIZE on non-plant tile"
        if inv.get("FERTILIZER", 0) <= 0:
            return "no FERTILIZER in inventory"
        return None

    if kind == "DIG":
        if isinstance(tile, Structure) and tile.animal is not None:
            return "DIG on structure with an animal (no-op)"
        if not isinstance(tile, Plant | Weed | Structure):
            return "DIG on empty tile"
        return None

    if kind in ("BUILD_COOP", "BUILD_PASTURE"):
        if not isinstance(tile, Empty):
            return f"{kind} on non-empty tile"
        return None

    if kind == "FEED":
        if not (isinstance(tile, Structure) and tile.animal is not None):
            return "FEED on non-animal tile"
        if tile.fed_today:
            return "already fed today (no-op)"
        if inv.get("WHEAT", 0) <= 0:
            return "no WHEAT in inventory"
        return None

    if kind == "CARE":
        if not (isinstance(tile, Structure) and tile.animal is not None):
            return "CARE on non-animal tile"
        if tile.cared_today:
            return "already cared today (no-op)"
        return None

    if kind == "COLLECT_FERTILIZER":
        if not (isinstance(tile, Structure) and tile.animal is not None):
            return "COLLECT_FERTILIZER on non-animal tile"
        if not tile.fertilizer_available:
            return "no fertilizer available on this animal"
        return None

    return f"unknown op {kind!r}"


def _check_market_order(obs: Observation, order: list[Any], hires_today: int) -> str | None:
    """Return a reason string if this market order is illegal, else None."""
    if not isinstance(order, list) or not order:
        return "empty or non-list order"
    op = order[0]
    money = obs.me.money

    if op == "HIRE":
        # Cost = fib(hires_today + 1) with fib starting 1,1,2,3,5,...
        cost = _fib(hires_today)
        if money < cost:
            return f"HIRE cost {cost} exceeds money {money:.0f}"
        return None

    if op == "BUY_LAND":
        extra = len(obs.me.unlocked_quadrants) - 1
        if extra >= len(LAND_ORDER):
            return "all quadrants already unlocked"
        cost = LAND_PRICES[extra]
        if money < cost:
            return f"BUY_LAND cost {cost} exceeds money {money:.0f}"
        return None

    if op in ("BUY_SEED", "BUY_PRODUCT", "BUY_ANIMAL", "SELL"):
        if len(order) < 3:
            return f"{op} missing arguments"
        item = order[1]
        try:
            n = int(order[2])
        except (TypeError, ValueError):
            return f"{op} non-integer quantity"
        if n <= 0:
            return f"{op} non-positive quantity {n}"

        if op == "SELL":
            if item not in PRODUCTS:
                return f"SELL unknown product {item!r}"
            if obs.private.shed.get(item, 0) <= 0:
                return f"no {item} in shed to sell"
            return None
        if op == "BUY_SEED":
            if item not in CROPS:
                return f"BUY_SEED unknown crop {item!r}"
            if money < CROPS[item]["seed"]:
                return f"cannot afford one {item} seed at {CROPS[item]['seed']} (money {money:.0f})"
            return None
        if op == "BUY_PRODUCT":
            if item not in BUYABLE_PRODUCTS:
                return f"BUY_PRODUCT unbuyable product {item!r}"
            price = obs.market.prices.get(item, 0)
            if money < price:
                return f"cannot afford one {item} at {price} (money {money:.0f})"
            return None
        if op == "BUY_ANIMAL":
            if item not in ANIMALS:
                return f"BUY_ANIMAL unknown animal {item!r}"
            cost = ANIMALS[item]["cost"]
            if money < cost:
                return f"cannot afford one {item} at {cost} (money {money:.0f})"
            return None

    return f"unknown market op {op!r}"


def _fib(n: int) -> int:
    """Fib indexed so fib(0)=1, fib(1)=1, fib(2)=2, ..."""
    a, b = 1, 1
    for _ in range(n):
        a, b = b, a + b
    return a


def check(obs: Observation, act: dict[str, Any], board_size: int = 10) -> list[Issue]:
    """Return a list of issues with the proposed action. Empty list means legal."""
    issues: list[Issue] = []

    farmer_op = act.get("farmer", ["PASS"])
    hands_ops = list(act.get("hands", []))
    market_orders = list(act.get("market", []))

    unit_ops = [farmer_op, *hands_ops]

    # Atomic multi-unit PLANT rule: if total PLANT requests for a crop exceed
    # available seeds, the env drops ALL PLANT requests for that crop this turn.
    plant_demand: dict[str, int] = {}
    for op in unit_ops:
        if isinstance(op, list) and len(op) >= 2 and op[0] == "PLANT":
            plant_demand[op[1]] = plant_demand.get(op[1], 0) + 1
    blocked_crops = {
        crop for crop, demand in plant_demand.items() if demand > obs.private.seeds.get(crop, 0)
    }

    for i, op in enumerate(unit_ops):
        if isinstance(op, list) and len(op) >= 2 and op[0] == "PLANT" and op[1] in blocked_crops:
            component: Component = "farmer" if i == 0 else "hands"
            idx = 0 if i == 0 else i - 1
            crop = op[1]
            if plant_demand[crop] > 1:
                block_reason = (
                    f"total PLANT {crop} demand ({plant_demand[crop]}) exceeds seed count "
                    f"({obs.private.seeds.get(crop, 0)}); env drops ALL PLANT {crop} this turn"
                )
            else:
                block_reason = f"no {crop} seeds"
            issues.append(Issue(component=component, index=idx, op=op, reason=block_reason))
            continue
        unit_reason = _check_unit_op(obs, i, op, board_size)
        if unit_reason is not None:
            component = "farmer" if i == 0 else "hands"
            idx = 0 if i == 0 else i - 1
            issues.append(Issue(component=component, index=idx, op=op, reason=unit_reason))

    for i, order in enumerate(market_orders):
        # HIRE cost climbs with hires_today; the env processes HIRE / BUY_LAND
        # atomically in order at the start of the market queue, so we approximate.
        market_reason = _check_market_order(obs, order, obs.me.hires_today)
        if market_reason is not None:
            issues.append(Issue(component="market", index=i, op=list(order), reason=market_reason))

    return issues
