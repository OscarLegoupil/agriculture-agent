"""Kaggriculture submission - agent v6 (2026-09-08).

A rewrite of the tile plan and the runtime that drives it.

v4 and v5 ran four tiles out of the twenty-five the NW quadrant starts with:
wheat, two carrots, one goose, one hired hand. The ceiling on that shape is
the main farmer's twenty-four turns per day, because the runner gave hands a
short fixed watering list and everything else to the farmer.

v6 replaces that runner with a priority scheduler. Every planned tile that
wants attention becomes a task; every worker takes the highest-priority task
it can reach in the fewest steps. Hands are cleared every night and cost
fib(n) coins to rehire, so nine of them cost 88 coins a day, and once the
crew is not the bottleneck the tile plan can be:

- Twelve structures on the tiles nearest the shed: four geese, four cows,
  four sheep. Every animal makes one fertilizer per day whatever its species,
  and fertilizer at 100 base is the single largest revenue line in the game.
  Feeding and caring an animal daily adds one product unit per day on top.
  Spreading the herd across three species spreads it across three product
  markets, and the milk and wool curves floor after 76 and 58 units.
- Thirteen melon tiles behind them. A melon reaches its six-unit cap at age
  ten for eight waterings, the best coins-per-worker-action of any crop, but
  its price curve is quadratic above I0 and floors after about 158 units.
- The melon tiles switch to carrot on day 20, the last day a fresh melon can
  still ripen inside the season.

The plan is the output of `kaggriculture.agent.route_agent.generate`, which
derives it from the allocator and then plays the shortlist out; the cached
route is `configs/routes/tuned/generated_expansion.yaml`. Hands ramp 4, 7, 9
over days 0, 2 and 5. The herd and the field are targets from day 0 and the
market policy fills them as cash allows: starting money is 3000 and the
twelve animals alone cost 5200. Feed is bought, not grown: a wheat tile
yields one unit a day and a melon tile earns a hundred.

Measured against the packaged starter agent on seeds 0-3 and 42: mean 82175
coins, worst 79600. v5 scores 9604 on seed 42.
"""

from __future__ import annotations

import time
from typing import Any

# ---------------------------------------------------------------------------
# Environment constants (transcribed from kaggle-environments 1.32.7).
# ---------------------------------------------------------------------------

_TURNS_PER_DAY = 24
_SEASON_DAYS = 30
_MAX_MARKET_ORDERS = 10
_SHED_ACCESS = ((4, 4), (5, 4), (4, 5), (5, 5))
_SHED_SET = frozenset(_SHED_ACCESS)
_LAND_PRICES = {"NE": 1000, "SW": 2000, "SE": 4000}

_CROPS = {
    "WHEAT": (10, 2, 4, 0, 6, False),
    "CARROT": (20, 2, 3, 0, 4, False),
    "TOMATO": (50, 8, 8, 1, 4, True),
    "STRAWBERRY": (100, 10, 10, 2, 4, True),
    "MELON": (80, 10, 12, 0, 6, False),
}  # seed, first_yield_day, max_yield_day, interval, max_yield, ongoing

_ANIMAL_COST = {"GOOSE": 300, "COW": 400, "SHEEP": 500}

_CARRIED = (
    "WHEAT",
    "CARROT",
    "TOMATO",
    "STRAWBERRY",
    "MELON",
    "EGG",
    "MILK",
    "WOOL",
    "FERTILIZER",
)

# ---------------------------------------------------------------------------
# Route (configs/routes/tuned/generated_expansion.yaml).
# ---------------------------------------------------------------------------

_GEESE = ((4, 4), (3, 4), (4, 3), (2, 4))
_COWS = ((3, 3), (4, 2), (1, 4), (2, 3))
_SHEEP = ((3, 2), (4, 1), (0, 4), (1, 3))
_FIELD = (
    (2, 2),
    (3, 1),
    (4, 0),
    (0, 3),
    (1, 2),
    (2, 1),
    (3, 0),
    (0, 2),
    (1, 1),
    (2, 0),
    (0, 1),
    (1, 0),
    (0, 0),
)

_STRUCTURES = (
    [(t, "COOP", "GOOSE") for t in _GEESE]
    + [(t, "PASTURE", "COW") for t in _COWS]
    + [(t, "PASTURE", "SHEEP") for t in _SHEEP]
)

# (from_day, structures used, field tiles used, field crop, hands)
_PHASES = (
    (0, 12, 13, "MELON", 4),
    (2, 12, 13, "MELON", 7),
    (5, 12, 13, "MELON", 9),
    (20, 12, 13, "CARROT", 9),
)

_SEED_BUY_ORDER = ("MELON", "CARROT")
_ANIMAL_BUY_ORDER = ("GOOSE", "COW", "SHEEP")
_SELL_ORDER = (
    "MELON",
    "WOOL",
    "MILK",
    "STRAWBERRY",
    "FERTILIZER",
    "TOMATO",
    "EGG",
    "CARROT",
    "WHEAT",
)
_LIQUIDATE_FROM_DAY = 28
_FEED_DAYS = 1
_MONEY_RESERVE = 0
_HIRE_UNTIL_HOUR = 5
_HIRES_PER_TURN = 2
_DROP_THRESHOLD = 4
_PICKUP_BATCH = 5
_TIME_BUDGET_SECONDS = 0.4

# Priority ladder. Lower runs first.
_P_CRITICAL = 0
_P_HARVEST = 1
_P_PLANT = 3
_P_WATER = 4
_P_CARE = 5
_P_COLLECT = 6
_P_DROP = 7


def _plan_for_day(day: int) -> tuple[list[Any], list[Any], int]:
    chosen = _PHASES[0]
    for phase in _PHASES:
        if phase[0] > day:
            break
        chosen = phase
    _, n_struct, n_field, crop, hands = chosen
    return _STRUCTURES[:n_struct], [(t, crop) for t in _FIELD[:n_field]], hands


# ---------------------------------------------------------------------------
# Yield model.
# ---------------------------------------------------------------------------


def _water_window(crop: str) -> tuple[int, int]:
    _, _, max_yield_day, _, _, ongoing = _CROPS[crop]
    if ongoing:
        return (1, 0)
    return ((max_yield_day + 1) // 2, max_yield_day)


def _target_units(crop: str, fertilized: bool = False) -> int:
    _, _, _, _, max_yield, ongoing = _CROPS[crop]
    if ongoing:
        return 1
    start, end = _water_window(crop)
    return min(max_yield, 1 + (end - start + 1) * (2 if fertilized else 1))


def _harvest_age(crop: str) -> int:
    _, first_yield_day, _, _, _, ongoing = _CROPS[crop]
    if ongoing:
        return first_yield_day
    start, _end = _water_window(crop)
    return max(first_yield_day, start + _target_units(crop) - 2)


# ---------------------------------------------------------------------------
# Scheduler.
# ---------------------------------------------------------------------------


def _distance(a: tuple[int, int], b: tuple[int, int]) -> int:
    return abs(a[0] - b[0]) + abs(a[1] - b[1])


def _step_towards(pos: tuple[int, int], target: tuple[int, int]) -> list[Any]:
    if pos[0] < target[0]:
        return ["EAST"]
    if pos[0] > target[0]:
        return ["WEST"]
    if pos[1] < target[1]:
        return ["SOUTH"]
    return ["NORTH"]


def _plant_tasks(
    tile: tuple[int, int],
    t: dict[str, Any],
    day: int,
    step: int,
    tasks: list[tuple[Any, ...]],
) -> None:
    crop = t["crop"]
    if crop not in _CROPS:
        return
    _, first_yield_day, _, _, _, ongoing = _CROPS[crop]
    age = day - int(t["planted_day"])
    fertilized = int(t.get("fertilized_until_day", -1)) >= day
    start, end = _water_window(crop)

    if not t.get("watered_today"):
        if int(t.get("consecutive_unwatered", 0)) >= 1:
            tasks.append((_P_CRITICAL, "WATER", tile, None, None, None))
        elif start <= age <= end:
            tasks.append((_P_WATER, "WATER", tile, None, None, None))

    units = int(t.get("yield_units", 0))
    lifespan = int(t.get("max_lifespan_step", -1))
    decaying = lifespan >= 0 and step >= lifespan - 1
    ripe = units >= _target_units(crop, fertilized)
    pickable = units > 0 and age >= first_yield_day
    if pickable and (ongoing or ripe or decaying or day >= _SEASON_DAYS - 1):
        tasks.append((_P_HARVEST, "HARVEST", tile, None, None, None))


def _structure_tasks(
    tile: tuple[int, int],
    t: dict[str, Any],
    animal: str,
    tasks: list[tuple[Any, ...]],
) -> None:
    if "animal" not in t:
        tasks.append((_P_HARVEST, "PLACE", tile, animal, animal, None))
        return
    fed = bool(t.get("fed_today", False))
    if not fed:
        level = _P_CRITICAL if int(t.get("consecutive_unfed", 0)) >= 1 else _P_CARE
        tasks.append((level, "FEED", tile, None, "WHEAT", None))
    if int(t.get("yield_units", 0)) > 0:
        tasks.append((_P_HARVEST, "HARVEST", tile, None, None, None))
    if fed and not t.get("cared_today"):
        tasks.append((_P_CARE, "CARE", tile, None, None, None))
    if t.get("fertilizer_available"):
        tasks.append((_P_COLLECT, "COLLECT_FERTILIZER", tile, None, None, None))


def _build_tasks(
    structures: list[Any],
    field: list[Any],
    tiles: list[list[Any]],
    day: int,
    hour: int,
    step: int,
    seeds: dict[str, int],
    shed: dict[str, int],
    inventories: list[dict[str, int]],
    n_workers: int,
) -> list[tuple[Any, ...]]:
    """Tasks are (priority, op, tile, arg, needs, worker)."""
    tasks: list[tuple[Any, ...]] = []
    stocked = dict(shed)
    for inventory in inventories:
        for item, n in inventory.items():
            stocked[item] = stocked.get(item, 0) + n

    for (x, y), kind, animal in structures:
        t = tiles[y][x]
        if isinstance(t, dict) and t.get("kind") == kind:
            if "animal" in t or stocked.get(animal, 0) > 0:
                _structure_tasks((x, y), t, animal, tasks)
        elif isinstance(t, dict) and t.get("kind") == "WEED":
            tasks.append((_P_PLANT, "DIG", (x, y), None, None, None))
        elif t is None:
            op = "BUILD_COOP" if kind == "COOP" else "BUILD_PASTURE"
            tasks.append((_P_PLANT, op, (x, y), None, None, None))

    budget = dict(seeds)
    plantable = hour <= _TURNS_PER_DAY - 3
    for (x, y), crop in field:
        t = tiles[y][x]
        if isinstance(t, dict) and t.get("kind") == "PLANT":
            _plant_tasks((x, y), t, day, step, tasks)
        elif isinstance(t, dict) and t.get("kind") == "WEED":
            tasks.append((_P_PLANT, "DIG", (x, y), None, None, None))
        elif t is None:
            if not plantable or budget.get(crop, 0) <= 0:
                continue
            if day + _harvest_age(crop) > _SEASON_DAYS - 1:
                continue
            budget[crop] -= 1
            tasks.append((_P_PLANT, "PLANT", (x, y), crop, None, None))

    last_turns = day >= _SEASON_DAYS - 1 and hour >= _TURNS_PER_DAY - 4
    threshold = 1 if last_turns else _DROP_THRESHOLD
    for index in range(n_workers):
        inventory = inventories[index] if index < len(inventories) else {}
        if sum(inventory.get(item, 0) for item in _CARRIED) >= threshold:
            tasks.append((_P_DROP, "DROP", None, None, None, index))
    return tasks


def _assign(
    tasks: list[tuple[Any, ...]],
    positions: list[tuple[int, int]],
    inventories: list[dict[str, int]],
    shed: dict[str, int],
) -> dict[int, list[Any]]:
    carrying = [dict(inventories[i]) if i < len(inventories) else {} for i in range(len(positions))]
    demand: dict[str, int] = {}
    for task in tasks:
        if task[4] is not None:
            demand[task[4]] = demand.get(task[4], 0) + 1

    ops: dict[int, list[Any]] = {}
    free = set(range(len(positions)))
    fetching: set[str] = set()

    def send(index: int, task: tuple[Any, ...]) -> None:
        _prio, op, tile, arg, needs, _worker = task
        position = positions[index]
        target = tile
        if target is None:
            target = min(_SHED_ACCESS, key=lambda s: _distance(position, s))
        if position == target:
            if op == "PLANT":
                ops[index] = ["PLANT", arg]
            elif op == "PLACE":
                ops[index] = ["PLACE", arg, 1]
            else:
                ops[index] = [op]
            if needs is not None:
                carrying[index][needs] = carrying[index].get(needs, 0) - 1
        else:
            ops[index] = _step_towards(position, target)
        free.discard(index)

    def fetch(item: str) -> None:
        want = min(demand.get(item, 1), shed.get(item, 0), _PICKUP_BATCH)
        if want <= 0:
            return
        index = min(free, key=lambda i: (min(_distance(positions[i], s) for s in _SHED_ACCESS), i))
        position = positions[index]
        if position in _SHED_SET:
            ops[index] = ["PICKUP", item, want]
        else:
            ops[index] = _step_towards(
                position, min(_SHED_ACCESS, key=lambda s: _distance(position, s))
            )
        free.discard(index)
        fetching.add(item)

    for task in sorted(tasks, key=lambda t: (t[0], t[1], t[2] or (-1, -1))):
        if not free:
            break
        _prio, _op, tile, _arg, needs, worker = task
        if worker is not None:
            if worker in free:
                send(worker, task)
            continue
        anchor = tile if tile is not None else _SHED_ACCESS[0]
        if needs is not None:
            carriers = [i for i in free if carrying[i].get(needs, 0) > 0]
            if not carriers:
                if needs not in fetching:
                    fetch(needs)
                continue
            send(min(carriers, key=lambda i: (_distance(positions[i], anchor), i)), task)
            continue
        send(min(free, key=lambda i: (_distance(positions[i], anchor), i)), task)
    return ops


# ---------------------------------------------------------------------------
# Market policy.
# ---------------------------------------------------------------------------


def _market_orders(
    structures: list[Any],
    field: list[Any],
    hands: int,
    tiles: list[list[Any]],
    day: int,
    hour: int,
    money: float,
    seeds: dict[str, int],
    shed: dict[str, int],
    inventories: list[dict[str, int]],
    prices: dict[str, int],
    hires_today: int,
) -> list[list[Any]]:
    head: list[list[Any]] = []
    if hour <= _HIRE_UNTIL_HOUR and hires_today < hands:
        head.extend([["HIRE"]] * min(hands - hires_today, _HIRES_PER_TURN))

    carried: dict[str, int] = {}
    for inventory in inventories:
        for item, n in inventory.items():
            carried[item] = carried.get(item, 0) + n

    placed = 0
    vacancies: dict[str, int] = {}
    for (x, y), kind, animal in structures:
        t = tiles[y][x]
        if isinstance(t, dict) and t.get("kind") == kind:
            if "animal" in t:
                placed += 1
            else:
                vacancies[animal] = vacancies.get(animal, 0) + 1

    feed_target = len(structures) * _FEED_DAYS
    wheat = shed.get("WHEAT", 0) + carried.get("WHEAT", 0)

    buys: list[list[Any]] = []
    budget = money
    if wheat < feed_target:
        price = max(1, int(prices.get("WHEAT", 25)))
        n = min(feed_target - wheat, int(max(0.0, budget) // price))
        if n > 0:
            buys.append(["BUY_PRODUCT", "WHEAT", n])
            budget -= n * price

    budget -= _MONEY_RESERVE
    owned = placed + sum(shed.get(a, 0) + carried.get(a, 0) for a in _ANIMAL_BUY_ORDER)
    headroom = wheat // max(1, _FEED_DAYS) - owned
    for animal in _ANIMAL_BUY_ORDER:
        if headroom <= 0:
            break
        cost = _ANIMAL_COST[animal]
        want = vacancies.get(animal, 0) - shed.get(animal, 0) - carried.get(animal, 0)
        n = min(want, headroom, int(max(0.0, budget) // cost))
        if n > 0:
            buys.append(["BUY_ANIMAL", animal, n])
            budget -= n * cost
            headroom -= n

    for crop in _SEED_BUY_ORDER:
        if day + _harvest_age(crop) > _SEASON_DAYS - 1:
            continue
        want = sum(1 for (x, y), c in field if c == crop and tiles[y][x] is None)
        want -= seeds.get(crop, 0)
        cost = _CROPS[crop][0]
        n = min(want, int(max(0.0, budget) // cost))
        if n > 0:
            buys.append(["BUY_SEED", crop, n])
            budget -= n * cost

    sells: list[list[Any]] = []
    for product in _SELL_ORDER:
        n = shed.get(product, 0)
        if product == "WHEAT":
            n -= feed_target
        if n > 0:
            sells.append(["SELL", product, n])

    room = max(0, _MAX_MARKET_ORDERS - len(head) - len(buys))
    return (head + sells[:room] + buys)[:_MAX_MARKET_ORDERS]


# ---------------------------------------------------------------------------
# Entry point.
# ---------------------------------------------------------------------------


def _pass_action(n_hands: int, market: list[list[Any]]) -> dict[str, Any]:
    return {"farmer": ["PASS"], "hands": [["PASS"] for _ in range(n_hands)], "market": market}


def agent(obs: dict[str, Any]) -> dict[str, Any]:
    start = time.perf_counter()
    farms = obs.get("farms", [])
    player = int(obs.get("player", 0))
    if not farms or player >= len(farms):
        return {"farmer": ["PASS"], "hands": [], "market": []}

    me = farms[player]
    tiles = me["tiles"]
    day = int(obs.get("day", 0))
    hour = int(obs.get("hour", 0))
    step = int(obs.get("step", day * _TURNS_PER_DAY + hour))
    private = obs.get("private", {}) or {}
    seeds = private.get("seeds", {}) or {}
    shed = private.get("shed", {}) or {}
    inventories = private.get("inventories", [{}]) or [{}]
    positions = [tuple(me["farmer"])] + [tuple(h) for h in me.get("hands", [])]
    prices = (obs.get("market", {}) or {}).get("prices", {}) or {}

    structures, field, hands = _plan_for_day(day)

    try:
        market = _market_orders(
            structures,
            field,
            hands,
            tiles,
            day,
            hour,
            float(me.get("money", 0.0)),
            seeds,
            shed,
            inventories,
            prices,
            int(me.get("hires_today", 0)),
        )
    except (KeyError, IndexError, ValueError, TypeError):
        market = []

    try:
        tasks = _build_tasks(
            structures, field, tiles, day, hour, step, seeds, shed, inventories, len(positions)
        )
        if time.perf_counter() - start > _TIME_BUDGET_SECONDS:
            return _pass_action(len(positions) - 1, market)
        ops = _assign(tasks, positions, inventories, shed)
    except (KeyError, IndexError, ValueError, TypeError):
        return _pass_action(len(positions) - 1, market)

    if time.perf_counter() - start > _TIME_BUDGET_SECONDS:
        return _pass_action(len(positions) - 1, market)
    return {
        "farmer": ops.get(0, ["PASS"]),
        "hands": [ops.get(i + 1, ["PASS"]) for i in range(len(positions) - 1)],
        "market": market,
    }
