"""Multi-worker priority scheduler.

The v4/v5 runner gives the main farmer one fixed decision tree and hands a
short watering list. That caps the farm at a handful of tiles, because every
extra tile competes for the farmer's 24 turns. This module replaces the tree
with a per-turn assignment problem: every planned tile that needs attention
becomes a task with a priority, and every worker (the farmer plus that day's
hired hands) takes the highest-priority task it can reach in the fewest
Manhattan steps.

Priority ladder, in order:

0. water a plant that turns to weed tonight, feed an animal that escapes tonight
1. harvest ripe crops and animal produce, place a bought animal in its structure
2. fertilize a plant inside its bonus window
3. plant an empty plan tile, clear a weed, build a missing structure
4. water a plant whose yield still grows today
5. feed and care for an animal that is not at risk
6. collect fertilizer
7. drop carried produce at the shed
8. pick up feed or an animal from the shed

Level 8 is implicit. A task that needs a carried item and finds no carrier
sends exactly one worker to the shed for it, which keeps a herd of unfed
animals from pulling the whole crew into a feed ferry every turn.

The scheduler holds no state between turns: `schedule` is a pure function of
(plan, observation).
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Final

from kaggriculture.env.constants import CROPS
from kaggriculture.env.observation import (
    Empty,
    Farm,
    Observation,
    Plant,
    Structure,
    Tile,
    Weed,
)

TURNS_PER_DAY: Final[int] = 24
SEASON_DAYS: Final[int] = 30

P_CRITICAL: Final[int] = 0
P_HARVEST: Final[int] = 1
P_FERTILIZE: Final[int] = 2
P_PLANT: Final[int] = 3
P_WATER: Final[int] = 4
P_CARE: Final[int] = 5
P_COLLECT: Final[int] = 6
P_DROP: Final[int] = 7
P_PICKUP: Final[int] = 8

# Produce a worker carries around. Seeds never enter an inventory.
_CARRIED_PRODUCE: Final[tuple[str, ...]] = (
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


@dataclass(frozen=True, slots=True)
class FarmPlan:
    """Target contents of every tile the farm should be running today.

    `crops` maps a tile to the crop that should grow on it, `structures` maps a
    tile to its (kind, animal) pair. `fertilize` lists the crops worth spending
    a fertilizer unit on; it is empty by default because fertilizer sells for
    more than the extra yield is worth on every crop in the game. `hands` is
    the hand count the day is budgeted for; issuing the hire order is market
    policy, the scheduler only reports it.
    """

    crops: dict[tuple[int, int], str] = field(default_factory=dict)
    structures: dict[tuple[int, int], tuple[str, str]] = field(default_factory=dict)
    fertilize: frozenset[str] = frozenset()
    hands: int = 0


@dataclass(frozen=True, slots=True)
class Task:
    """One unit of work for one worker on one tile."""

    priority: int
    op: str
    tile: tuple[int, int] | None = None  # None routes the worker to the shed
    arg: str | None = None
    needs: str | None = None  # item the worker must carry to act
    worker: int | None = None  # pin the task to one worker


def water_window(crop: str) -> tuple[int, int]:
    """Inclusive plant-age range in which watering adds yield.

    Ongoing crops produce on a schedule whether or not they were watered, so
    their window is empty and watering them is survival only.
    """
    spec = CROPS[crop]
    if spec["ongoing"]:
        return (1, 0)
    return ((spec["max_yield_day"] + 1) // 2, spec["max_yield_day"])


def target_units(crop: str, *, fertilized: bool = False) -> int:
    """Yield units a fully watered plant holds at the end of its window."""
    spec = CROPS[crop]
    if spec["ongoing"]:
        return 1
    start, end = water_window(crop)
    gain = (end - start + 1) * (2 if fertilized else 1)
    return min(spec["max_yield"], 1 + gain)


def harvest_age(crop: str) -> int:
    """Earliest plant age at which a full harvest is available."""
    spec = CROPS[crop]
    if spec["ongoing"]:
        return spec["first_yield_day"]
    start, _ = water_window(crop)
    return max(spec["first_yield_day"], start + target_units(crop) - 2)


def shed_access_tiles(board_size: int) -> tuple[tuple[int, int], ...]:
    """The four inner-corner tiles the shed can be reached from."""
    half = board_size // 2
    return ((half - 1, half - 1), (half, half - 1), (half - 1, half), (half, half))


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


def _tile_at(farm: Farm, tile: tuple[int, int]) -> Tile | None:
    x, y = tile
    if not (0 <= y < len(farm.tiles) and 0 <= x < len(farm.tiles[y])):
        return None
    return farm.tiles[y][x]


def _carried(inventory: dict[str, int]) -> int:
    return sum(inventory.get(item, 0) for item in _CARRIED_PRODUCE)


def _plant_tasks(
    tile: tuple[int, int],
    plant: Plant,
    *,
    obs: Observation,
    fertilize: frozenset[str],
) -> list[Task]:
    spec = CROPS[plant.crop]
    age = obs.day - plant.planted_day
    fertilized = plant.fertilized_until_day >= obs.day
    start, end = water_window(plant.crop)
    tasks: list[Task] = []

    if not plant.watered_today:
        if plant.consecutive_unwatered >= 1:
            tasks.append(Task(P_CRITICAL, "WATER", tile))
        elif start <= age <= end:
            tasks.append(Task(P_WATER, "WATER", tile))

    decaying = plant.max_lifespan_step >= 0 and obs.step >= plant.max_lifespan_step - 1
    ripe = plant.yield_units >= target_units(plant.crop, fertilized=fertilized)
    season_over = obs.day >= SEASON_DAYS - 1
    pickable = plant.yield_units > 0 and age >= spec["first_yield_day"]
    if pickable and (spec["ongoing"] or ripe or decaying or season_over):
        tasks.append(Task(P_HARVEST, "HARVEST", tile))

    gains = target_units(plant.crop, fertilized=True) > target_units(plant.crop)
    if plant.crop in fertilize and gains and not fertilized and start <= age < end:
        tasks.append(Task(P_FERTILIZE, "FERTILIZE", tile, needs="FERTILIZER"))
    return tasks


def _structure_tasks(
    tile: tuple[int, int],
    animal: str,
    structure: Structure,
) -> list[Task]:
    if structure.animal is None:
        return [Task(P_HARVEST, "PLACE", tile, arg=animal, needs=animal)]

    tasks: list[Task] = []
    if not structure.fed_today:
        level = P_CRITICAL if structure.consecutive_unfed >= 1 else P_CARE
        tasks.append(Task(level, "FEED", tile, needs="WHEAT"))
    if structure.yield_units > 0:
        tasks.append(Task(P_HARVEST, "HARVEST", tile))
    if structure.fed_today and not structure.cared_today:
        tasks.append(Task(P_CARE, "CARE", tile))
    if structure.fertilizer_available:
        tasks.append(Task(P_COLLECT, "COLLECT_FERTILIZER", tile))
    return tasks


def build_tasks(
    plan: FarmPlan,
    obs: Observation,
    *,
    drop_threshold: int = 4,
) -> list[Task]:
    """Every action the farm wants taken this turn, unassigned."""
    farm = obs.me
    tasks: list[Task] = []

    for tile, (kind, animal) in plan.structures.items():
        current = _tile_at(farm, tile)
        if isinstance(current, Structure):
            tasks.extend(_structure_tasks(tile, animal, current))
        elif isinstance(current, Weed):
            tasks.append(Task(P_PLANT, "DIG", tile))
        elif isinstance(current, Empty):
            op = "BUILD_COOP" if kind == "COOP" else "BUILD_PASTURE"
            tasks.append(Task(P_PLANT, op, tile))

    seed_budget = dict(obs.private.seeds)
    plantable = obs.hour <= TURNS_PER_DAY - 3
    for tile, crop in plan.crops.items():
        current = _tile_at(farm, tile)
        if isinstance(current, Plant):
            tasks.extend(_plant_tasks(tile, current, obs=obs, fertilize=plan.fertilize))
        elif isinstance(current, Weed):
            tasks.append(Task(P_PLANT, "DIG", tile))
        elif isinstance(current, Empty):
            if not plantable or seed_budget.get(crop, 0) <= 0:
                continue
            if obs.day + harvest_age(crop) > SEASON_DAYS - 1:
                continue
            seed_budget[crop] -= 1
            tasks.append(Task(P_PLANT, "PLANT", tile, arg=crop))

    # Carried produce is auto-dropped at day end, so mid-day drops exist only to
    # get stock into the shed early enough to sell it.
    inventories = obs.private.inventories
    last_turns = obs.day >= SEASON_DAYS - 1 and obs.hour >= TURNS_PER_DAY - 4
    threshold = 1 if last_turns else drop_threshold
    for index in range(1 + len(farm.hands)):
        inventory = inventories[index] if index < len(inventories) else {}
        if _carried(inventory) >= threshold:
            tasks.append(Task(P_DROP, "DROP", worker=index))
    return tasks


def assign(
    tasks: list[Task],
    obs: Observation,
    *,
    pickup_batch: int = 5,
) -> dict[int, list[Any]]:
    """Map worker index to the op it should run this turn.

    Tasks are consumed in priority order. Each one takes the nearest still-free
    worker, and a task whose `needs` item nobody carries sends a single worker
    to the shed for it. Workers left without a task are absent from the result
    and pass.
    """
    farm = obs.me
    shed = shed_access_tiles(len(farm.tiles))
    positions = [farm.farmer, *farm.hands]
    stored = obs.private.inventories
    carrying = [dict(stored[i]) if i < len(stored) else {} for i in range(len(positions))]

    demand: dict[str, int] = {}
    for task in tasks:
        if task.needs is not None:
            demand[task.needs] = demand.get(task.needs, 0) + 1

    ops: dict[int, list[Any]] = {}
    free = set(range(len(positions)))
    fetching: set[str] = set()

    def send(index: int, task: Task) -> None:
        position = positions[index]
        target = task.tile
        if target is None:
            target = min(shed, key=lambda s: _distance(position, s))
        if position == target:
            if task.op == "PLANT":
                ops[index] = ["PLANT", task.arg]
            elif task.op == "PLACE":
                ops[index] = ["PLACE", task.arg, 1]
            else:
                ops[index] = [task.op]
            if task.needs is not None:
                carrying[index][task.needs] = carrying[index].get(task.needs, 0) - 1
        else:
            ops[index] = _step_towards(position, target)
        free.discard(index)

    def fetch(item: str) -> None:
        want = min(demand.get(item, 1), obs.private.shed.get(item, 0), pickup_batch)
        if want <= 0:
            return
        index = min(free, key=lambda i: (min(_distance(positions[i], s) for s in shed), i))
        position = positions[index]
        if position in shed:
            ops[index] = ["PICKUP", item, want]
        else:
            ops[index] = _step_towards(position, min(shed, key=lambda s: _distance(position, s)))
        free.discard(index)
        fetching.add(item)

    for task in sorted(tasks, key=lambda t: (t.priority, t.op, t.tile or (-1, -1))):
        if not free:
            break
        if task.worker is not None:
            if task.worker in free:
                send(task.worker, task)
            continue
        anchor = task.tile if task.tile is not None else shed[0]
        if task.needs is not None:
            carriers = [i for i in free if carrying[i].get(task.needs, 0) > 0]
            if not carriers:
                if task.needs not in fetching:
                    fetch(task.needs)
                continue
            send(min(carriers, key=lambda i: (_distance(positions[i], anchor), i)), task)
            continue
        send(min(free, key=lambda i: (_distance(positions[i], anchor), i)), task)
    return ops


def schedule(
    plan: FarmPlan,
    obs: Observation,
    *,
    market: list[list[Any]] | None = None,
    drop_threshold: int = 4,
    time_budget_seconds: float = 0.4,
) -> dict[str, Any]:
    """Full action dict for one turn.

    Falls back to an all-PASS turn if assignment overruns
    `time_budget_seconds` or the observation cannot be interpreted, so a slow
    or malformed turn costs one turn instead of the episode.
    """
    start = time.perf_counter()
    n_hands = len(obs.me.hands)
    try:
        tasks = build_tasks(plan, obs, drop_threshold=drop_threshold)
        if time.perf_counter() - start > time_budget_seconds:
            return pass_action(n_hands, market)
        ops = assign(tasks, obs)
    except (KeyError, IndexError, ValueError, TypeError):
        return pass_action(n_hands, market)
    if time.perf_counter() - start > time_budget_seconds:
        return pass_action(n_hands, market)
    return {
        "farmer": ops.get(0, ["PASS"]),
        "hands": [ops.get(i + 1, ["PASS"]) for i in range(n_hands)],
        "market": list(market or []),
    }


def pass_action(n_hands: int, market: list[list[Any]] | None = None) -> dict[str, Any]:
    """An action dict where every worker passes."""
    return {
        "farmer": ["PASS"],
        "hands": [["PASS"] for _ in range(n_hands)],
        "market": list(market or []),
    }
