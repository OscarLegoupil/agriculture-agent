"""Price marginal daily labor from observed work and approximate routing cost.

The travel estimate is a screening model, not an executable route or a claimed
upper bound on avoidable wages. Season screens must measure displaced production.
"""

import gzip
import hashlib
import inspect
import math
from collections import Counter
from pathlib import Path

from kaggriculture.agent.competitive import ANIMALS, CROPS

INCUMBENT = "64fe323936dc9494add413eb956b0294658a88efe28572332c94676c68a09325"


def labor_tree_cost(points, depots):
    """Manhattan spanning forest rooted at shed access; optimistic connectivity."""
    pending = {
        point: min(abs(point[0] - d[0]) + abs(point[1] - d[1]) for d in depots) for point in points
    }
    cost = 0
    while pending:
        point = min(pending, key=lambda p: (pending[p], p))
        cost += pending.pop(point)
        for other in pending:
            pending[other] = min(
                pending[other], abs(point[0] - other[0]) + abs(point[1] - other[1])
            )
    return cost


def daily_labor_work(obs, configuration=None):
    """Remaining service, inputs and funded commissioning from the public state.

    Values are conservative current-quote service priorities, not additive season
    profit. Maintenance and harvesting can protect the same inventory; this
    heuristic should not be used as a farm investment objective.
    """
    cfg = configuration or {}
    day, hour = obs["day"], obs["hour"]
    farm = obs["farms"][obs["player"]]
    private = obs["private"]
    prices = obs["market"]["prices"]
    half = len(farm["tiles"]) // 2
    depots = [(half - 1, half - 1), (half, half - 1), (half - 1, half), (half, half)]
    operations, sites = Counter(), set()
    values = []
    urgent = 0
    inputs = Counter()
    outputs = 0
    free = []
    plants = 0
    inventories = private["inventories"]
    stock = Counter(private["shed"])
    carried = Counter()
    for inventory in inventories:
        stock.update(inventory)
        carried.update(inventory)

    def add(point, op, value, survival=False):
        nonlocal urgent
        operations[op] += 1
        sites.add(point)
        values.append(max(1.0, value))
        urgent += bool(survival)

    for y, row in enumerate(farm["tiles"]):
        for x, tile in enumerate(row):
            point = (x, y)
            if tile is None or (
                isinstance(tile, dict)
                and tile.get("kind") in ("WEED", "COOP", "PASTURE")
                and "animal" not in tile
            ):
                free.append((point, tile))
            if not isinstance(tile, dict):
                continue
            if "animal" in tile:
                _, first, interval, cap, product, _ = ANIMALS[tile["animal"]]
                age = day - tile["placed_day"]
                next_event = (
                    day + max(1, first - age)
                    if age < first
                    else day + interval - (age - first) % interval
                )
                useful = next_event <= 29 or tile["yield_units"] > 0
                price = prices[product]
                if not tile["fed_today"] and useful:
                    add(point, "FEED", price / interval, tile["consecutive_unfed"] > 0)
                    inputs["WHEAT"] += 1
                # Feeding later today unlocks care: count the prerequisite chain,
                # unlike a task list that sees only currently legal CARE actions.
                if not tile["cared_today"] and useful:
                    add(point, "CARE", price / interval * 0.6)
                if tile["fertilizer_available"] and day < 29:
                    add(point, "COLLECT_FERTILIZER", prices["FERTILIZER"] * 0.7)
                    outputs += 1
                if tile["yield_units"]:
                    add(point, "HARVEST", min(cap, tile["yield_units"]) * price * 0.7)
                    outputs += tile["yield_units"]
            elif tile.get("kind") == "PLANT":
                plants += 1
                crop = tile["crop"]
                _, first, last, interval, cap = CROPS[crop]
                age = day - tile["planted_day"]
                units = tile["yield_units"]
                exhausted = interval and age >= first + (cap - 1) * interval and not units
                if exhausted:
                    if day < 27:
                        add(point, "DIG", 8)
                    continue
                growth = (
                    (last + 1) // 2 <= age <= last
                    if not interval
                    else age + 1 >= first
                    and (age + 1 - first) % interval == 0
                    and (age + 1 - first) // interval < cap
                )
                if not tile["watered_today"] and (tile["consecutive_unwatered"] or growth):
                    add(point, "WATER", prices[crop] * 0.5, tile["consecutive_unwatered"] > 0)
                if age >= first and units:
                    target = 2 if interval else min(cap, 1 + last - (last + 1) // 2 + 1)
                    expires = tile["max_lifespan_step"]
                    due = (
                        units >= target
                        or (crop == "WHEAT" and (farm["money"] < 600 or stock["WHEAT"] < 18))
                        or (expires >= 0 and obs["step"] + 24 >= expires)
                    )
                    # Annual WATER can create today's final harvest increment.
                    if due or (not interval and growth and not tile["watered_today"]):
                        add(
                            point,
                            "HARVEST",
                            (units + (not interval and growth)) * prices[crop] * 0.7,
                        )
                        outputs += units + bool(not interval and growth)
                if (
                    interval
                    and growth
                    and tile["fertilized_until_day"] < day
                    and prices[crop] > prices["FERTILIZER"] * 0.7 + 10
                ):
                    add(point, "FERTILIZE", max(1, prices[crop] - prices["FERTILIZER"] * 0.7))
                    inputs["FERTILIZER"] += 1

    # Honor paid animal/seed inventories and a bounded amount of affordable
    # commissioning. This prevents a maintenance-only model from starving growth.
    free.sort(
        key=lambda cell: (
            min(abs(cell[0][0] - d[0]) + abs(cell[0][1] - d[1]) for d in depots),
            cell[0],
        )
    )
    held_animals = sum(stock.get(animal, 0) for animal in ANIMALS)
    for point, tile in free[:held_animals]:
        for op in (("DIG",) if tile and tile.get("kind") == "WEED" else ()) + (
            "BUILD",
            "PLACE_ANIMAL",
            "FEED",
            "CARE",
            "COLLECT_FERTILIZER",
        ):
            add(point, op, 30)
        inputs["WHEAT"] += 1
        outputs += 1
    free = free[held_animals:]
    crop = "STRAWBERRY" if day < 15 else "WHEAT"
    cash_reserve = 200 + inputs["WHEAT"] * prices["WHEAT"]
    affordable = max(0, int((farm["money"] - cash_reserve) / CROPS[crop][0]))
    funded = sum(private["seeds"].values()) + min(8, affordable)
    starts = min(len(free), max(0, 50 - plants), funded) if day < 27 else 0
    for point, tile in free[:starts]:
        if tile:
            add(point, "DIG", 12)
        add(point, "PLANT", 30)
        add(point, "WATER", 30, True)

    pickup_actions = sum(
        math.ceil(max(0, amount - carried.get(item, 0)) / batch)
        for item, batch in (("WHEAT", 3), ("FERTILIZER", 4))
        for amount in [inputs[item]]
    )
    delivery_actions = math.ceil((outputs + sum(carried.values())) / 5)
    tree = labor_tree_cost(sites, depots)
    mean_distance = (
        sum(min(abs(p[0] - d[0]) + abs(p[1] - d[1]) for d in depots) for p in sites) / len(sites)
        if sites
        else 0
    )
    # The connectivity term understates repeated visits. Add an explicit 25%
    # allowance and 60% of a depot leg per expected pickup/delivery. These are
    # declared approximations to calibrate against official replay behavior.
    travel = 1.25 * tree + 0.6 * mean_distance * (pickup_actions + delivery_actions)
    service = sum(operations.values())
    total = service + pickup_actions + delivery_actions + travel
    return {
        "operations": dict(operations),
        "service_actions": service,
        "urgent_actions": urgent,
        "input_pickups": pickup_actions,
        "deliveries": delivery_actions,
        "tree_distance": tree,
        "estimated_travel": travel,
        "estimated_work": total,
        "service_value": sum(values),
        "funded_crop_starts": starts,
        "hours_remaining": max(0, cfg.get("turnsPerDay", 24) - hour),
    }


def labor_calendar_plan(obs, configuration=None):
    """Choose extra capacity only while modeled marginal value exceeds wages."""
    cfg = configuration or {}
    model = daily_labor_work(obs, cfg)
    farm = obs["farms"][obs["player"]]
    existing = len(farm["hands"])
    remaining = model["hours_remaining"]
    # Current workers act now; hires act from the next decision. The efficiency
    # allowance covers imperfect distribution and interrupted task assignments.
    capacity = (existing + 1) * remaining * 0.88
    contribution = max(0, remaining - 1) * 0.88
    value_per_action = model["service_value"] / max(1, model["estimated_work"])
    cash = farm["money"]
    a, b = 1, 1
    for _ in range(farm["hires_today"]):
        a, b = b, a + b
    target = existing
    decisions = []
    while target < 12 and contribution:
        wage = a * int(cfg.get("farmHandCostMult", 1))
        served = min(contribution, max(0, model["estimated_work"] - capacity))
        marginal_value = served * value_per_action
        required = capacity < model["urgent_actions"] * 2
        buy = cash > wage + 120 and served > 0 and (required or marginal_value > wage)
        decisions.append(
            {"hand": target + 1, "wage": wage, "marginal_value": marginal_value, "buy": buy}
        )
        if not buy:
            break
        target += 1
        capacity += contribution
        cash -= wage
        a, b = b, a + b
    return {**model, "target_hands": target, "marginal_hires": decisions}


def build():
    """Embed helpers before the final agent declaration for official loader parity."""
    content = gzip.decompress((Path("reports/sources") / f"{INCUMBENT}.py.gz").read_bytes())
    assert hashlib.sha256(content).hexdigest() == INCUMBENT
    source = content.decode()
    helpers = "\n\n".join(
        inspect.getsource(function)
        for function in (labor_tree_cost, daily_labor_work, labor_calendar_plan)
    )
    source = source.replace("def agent(obs:", helpers + "\n\ndef agent(obs:", 1)
    old = '    target_hands = min(p["hands"], max(4, math.ceil(workload / 8)))\n    if day == 29:'
    assert source.count(old) == 1
    source = source.replace(
        old,
        '    target_hands = min(p["hands"], max(4, math.ceil(workload / 8)))\n'
        "    # Startup and paid animal queues retain their commissioning capacity.\n"
        "    if 15 <= day < 29 and hour < 8 and not any(stock[a] for a in ANIMALS):\n"
        '        target_hands = labor_calendar_plan(obs, cfg)["target_hands"]\n'
        "    if day == 29:",
        1,
    )
    compile(source, "labor_calendar", "exec")
    return source
