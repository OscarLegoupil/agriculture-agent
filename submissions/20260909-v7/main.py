"""Finite-season investment policy and coordinated value-per-action scheduling.

Self-contained deployment module. Constants follow kaggle-environments 1.32.7.
"""

from __future__ import annotations

import math
import sys
import time
from collections import Counter, defaultdict
from collections.abc import Sequence
from typing import Any

# seed, first production, final growth day, interval, production/holding cap
CROPS = {
    "WHEAT": (10, 2, 4, 0, 6),
    "CARROT": (20, 2, 3, 0, 4),
    "TOMATO": (50, 8, 8, 1, 4),
    "STRAWBERRY": (100, 10, 10, 2, 4),
    "MELON": (80, 10, 12, 0, 6),
}
ANIMALS = {
    "COW": (400, 8, 2, 6, "MILK", "PASTURE"),
    "SHEEP": (500, 6, 3, 6, "WOOL", "PASTURE"),
    "GOOSE": (300, 4, 1, 4, "EGG", "COOP"),
}
BASE = dict(
    WHEAT=25,
    CARROT=35,
    TOMATO=60,
    STRAWBERRY=120,
    MELON=250,
    EGG=50,
    MILK=160,
    WOOL=200,
    FERTILIZER=100,
)
SHOPS = {
    "BAKERY": ("EGG", "WHEAT"),
    "PIZZA_SHOP": ("MILK", "TOMATO", "WHEAT"),
    "BRUNCH_SPOT": ("EGG", "WHEAT", "STRAWBERRY"),
    "YARN_STORE": ("WOOL",),
    "ICE_CREAM_SHOP": ("STRAWBERRY", "MILK", "WHEAT"),
    "PET_CAFE": ("CARROT",),
    "SMOOTHIE_SHOP": ("STRAWBERRY", "MILK"),
    "FARMERS_MARKET": ("WHEAT", "CARROT", "TOMATO", "STRAWBERRY"),
}
PARAMS: dict[str, Any] = {
    "hands": 11,
    "quadrants": 2,
    "cows": 4,
    "sheep": 6,
    "geese": 8,
    "crop_tiles": 30,
    "fertilize": True,
    "care": True,
    "animal_stop": 16,
    "return_load": 5,
    "feed_grown": 8,
    "deadline_boost": 500,
    "feed_priority": 90,
    "crop_bias": {},
    "batch_harvest": False,
    "opening_geese": 0,
    "sell_batch": 100,
    "matching": True,
}


def minimum_assignment(cost: list[list[float]], budget_seconds: float = 0.15) -> list[int]:
    """Rectangular minimum-cost matching using augmenting paths and dual prices.

    Rows are workers; columns are destinations (including idle destinations).
    Running time is O(workers squared times destinations), bounded by farm size.
    """
    n = len(cost)
    if not n:
        return []
    m = len(cost[0])
    if m < n or any(len(row) != m for row in cost):
        raise ValueError("Assignment requires a rectangular matrix with columns >= rows")
    deadline = time.perf_counter() + budget_seconds
    available = set(range(m))
    fallback = []
    for row_cost in cost:
        column = min(available, key=lambda c: (row_cost[c], c))
        fallback.append(column)
        available.remove(column)
    row_price = [0.0] * (n + 1)
    col_price = [0.0] * (m + 1)
    occupied = [0] * (m + 1)
    previous = [0] * (m + 1)
    for row in range(1, n + 1):
        occupied[0] = row
        current = 0
        slack = [math.inf] * (m + 1)
        visited = [False] * (m + 1)
        while True:
            if time.perf_counter() >= deadline:
                print("assignment_budget_fallback", file=sys.stderr)
                return fallback
            visited[current] = True
            active = occupied[current]
            delta, next_col = math.inf, 0
            for column in range(1, m + 1):
                if visited[column]:
                    continue
                reduced = cost[active - 1][column - 1] - row_price[active] - col_price[column]
                if reduced < slack[column]:
                    slack[column], previous[column] = reduced, current
                if slack[column] < delta:
                    delta, next_col = slack[column], column
            for column in range(m + 1):
                if visited[column]:
                    row_price[occupied[column]] += delta
                    col_price[column] -= delta
                else:
                    slack[column] -= delta
            current = next_col
            if occupied[current] == 0:
                break
        while current:
            predecessor = previous[current]
            occupied[current] = occupied[predecessor]
            current = predecessor
    result = [-1] * n
    for column in range(1, m + 1):
        if occupied[column]:
            result[occupied[column] - 1] = column - 1
    return result


def distance(a: Sequence[int], b: Sequence[int]) -> int:
    return abs(a[0] - b[0]) + abs(a[1] - b[1])


def move(a: Sequence[int], b: Sequence[int]) -> list[Any]:
    if a[0] != b[0]:
        return ["EAST" if a[0] < b[0] else "WEST"]
    if a[1] != b[1]:
        return ["SOUTH" if a[1] < b[1] else "NORTH"]
    return ["PASS"]


def crop_value(
    crop: str, day: int, price: float, fertilizer_price: float, fertilize: bool
) -> float:
    """Net receipts of a new cohort before day 29, with an action charge.

    No recurring average income is credited before maturity. Estimates charge
    purchased inputs even when home produced, using their opportunity cost.
    """
    seed, first, last, interval, cap = CROPS[crop]
    remaining = 29 - day
    if remaining < first:
        return -math.inf
    if interval:
        events = min(cap, 1 + (remaining - first) // interval)
        life = first + (events - 1) * interval
        applications = math.ceil(events * interval / 3) if fertilize else 0
        units = events * (2 if fertilize else 1)
        actions = 2 + life / 2 + events + applications * 2 + (events if fertilize else 0)
    else:
        life = min(last, remaining)
        waters = max(0, life - (last + 1) // 2 + 1)
        units = min(cap, 1 + waters * (2 if fertilize else 1))
        applications = math.ceil(waters / 3) if fertilize else 0
        actions = 3 + life / 2 + applications * 2
    net = units * price - seed - applications * fertilizer_price
    return (net - actions * 4) / (life + 1)


def agent(obs: dict[str, Any], configuration: dict[str, Any] | None = None) -> dict[str, Any]:
    """Pure observation policy: no episode globals or repository imports."""
    if not obs.get("farms") or obs.get("player") not in (0, 1):
        return {"farmer": ["PASS"], "hands": [], "market": []}
    cfg = configuration or {}
    p = PARAMS
    day, hour = obs["day"], obs["hour"]
    farm = obs["farms"][obs["player"]]
    private = obs["private"]
    board = farm["tiles"]
    size = len(board)
    half = size // 2
    shed_tiles = [(half - 1, half - 1), (half, half - 1), (half - 1, half), (half, half)]
    positions = [tuple(farm["farmer"]), *map(tuple, farm["hands"])]
    inventories = [dict(i) for i in private["inventories"]]
    shed = dict(private["shed"])
    seeds = dict(private["seeds"])
    prices = obs["market"]["prices"]
    cells = [
        (x, y, tile)
        for y, row in enumerate(board)
        for x, tile in enumerate(row)
        if tile != "LOCKED"
    ]
    animals = [(x, y, t) for x, y, t in cells if isinstance(t, dict) and "animal" in t]
    plants = [(x, y, t) for x, y, t in cells if isinstance(t, dict) and t.get("kind") == "PLANT"]
    counts = Counter(t["animal"] for _, _, t in animals)
    crops = Counter(t["crop"] for _, _, t in plants)
    carried: Counter[str] = Counter()
    for inv in inventories:
        carried.update(inv)
    stock = Counter(shed) + carried
    market = []
    cash = farm["money"]
    feed_need = sum(not t["fed_today"] for _, _, t in animals) if day < 29 else 0
    fert_price = prices["FERTILIZER"]

    # Sell before buying. Unit-price impact is handled by the interpreter.
    # Keep only near-term inputs; large buffers compete with harvest storage.
    for item in BASE:
        reserve = max(0, len(animals) - carried["WHEAT"]) if item == "WHEAT" and day < 29 else 0
        if item == "FERTILIZER" and p["fertilize"] and day < 29:
            reserve = max(0, min(10, len(plants) // 2) - carried[item])
        quantity = max(0, shed.get(item, 0) - reserve)
        if sum(shed.values()) < 70 and day < 29:
            quantity = min(quantity, p["sell_batch"])
        if quantity:
            market.append(["SELL", item, quantity])
            # Conservative working capital: do not spend unexecuted sale quotes.

    # Demand forecasts use current shops and the expected composition of new
    # unlocks. Existing opponent crops and herds penalize saturated products.
    demand = Counter({item: 1.0 for item in BASE})
    for shop in obs["town"]["unlocked_shops"]:
        for item in SHOPS[shop]:
            demand[item] += 12 if len(SHOPS[shop]) == 1 else 6
    future_shops = max(0, min(8, (day + 8) // 3) - len(obs["town"]["unlocked_shops"]))
    for products in SHOPS.values():
        for item in products:
            demand[item] += future_shops * (12 if len(products) == 1 else 6) / 8
    supply: dict[str, float] = defaultdict(float)
    for other in obs["farms"]:
        for row in other["tiles"]:
            for tile in row:
                if not isinstance(tile, dict):
                    continue
                if "animal" in tile:
                    _, _, interval, _, product, _ = ANIMALS[tile["animal"]]
                    supply[product] += 1 + 1 / interval
                elif tile.get("kind") == "PLANT":
                    crop = tile["crop"]
                    spec = CROPS[crop]
                    supply[crop] += 8 / 17 if spec[3] else 4 / (spec[2] + 1)
    forecast = {
        item: max(
            BASE[item] * 0.15,
            (prices[item] * 0.65 + BASE[item] * 0.35)
            * min(1.6, max(0.25, (demand[item] + 8) / (supply[item] + 8))),
        )
        for item in BASE
    }

    # Investment is bounded by remaining production events and cash. Asset ages
    # come directly from observations and survive every daily planning checkpoint.
    desired = dict(COW=p["cows"], SHEEP=p["sheep"], GOOSE=p["geese"])
    purchase = None
    if day <= p["animal_stop"]:
        options = []
        for animal, cap in desired.items():
            cost, first, interval, _, product, _ = ANIMALS[animal]
            if counts[animal] + stock[animal] >= cap:
                continue
            events = max(0, 1 + (28 - day - first) // interval)
            revenue = events * (interval + 1) * forecast[product]
            feed_cost = (29 - day) * prices["WHEAT"]
            net = revenue - cost - feed_cost - (29 - day) * 12
            if net > 0 and cash > cost + max(150, feed_need * prices["WHEAT"]):
                options.append((net / cost, animal))
        if options and len(animals) < len(cells) - 2:
            purchase = max(options)[1]
        if day < 4 and counts["GOOSE"] + stock["GOOSE"] < p["opening_geese"] and cash > 500:
            purchase = "GOOSE"

    # Labour has Fibonacci marginal costs. Scale with service load; the cap is
    # an experimental parameter, not an assumption that more hands always pay.
    workload = len(plants) * 1.4 + len(animals) * 4.5
    target_hands = min(p["hands"], max(4, math.ceil(workload / 8)))
    if day == 29:
        target_hands = min(p["hands"], max(4, math.ceil(workload / 8)))
    if hour < 8:
        a, b = 1, 1
        for index in range(target_hands):
            if index >= len(farm["hands"]) and cash > a + 120 and len(market) < 8:
                market.append(["HIRE"])
                cash -= a
            a, b = b, a + b
    buy_feed = max(0, feed_need - stock["WHEAT"])
    if day < 29 and buy_feed and cash > buy_feed * (prices["WHEAT"] + 1):
        market.append(["BUY_PRODUCT", "WHEAT", buy_feed])
        cash -= buy_feed * (prices["WHEAT"] + 1)
    if purchase and cash > ANIMALS[purchase][0] + 150:
        market.append(["BUY_ANIMAL", purchase, 1])
        cash -= ANIMALS[purchase][0]
    if (
        len(farm["unlocked_quadrants"]) < p["quadrants"]
        and day < 15
        and len(plants) + len(animals) >= len(cells) - 4
    ):
        cost = (1000, 2000, 4000)[len(farm["unlocked_quadrants"]) - 1]
        if cash > cost + 1000:
            market.append(["BUY_LAND"])
            cash -= cost

    # Each task has a value and a destination. Prerequisite pickups are assigned
    # in the same matching pass, and shared stock, seeds and tiles are reserved.
    tasks = []

    def task(
        x: int, y: int, op: str, value: float, item: str | None = None, arg: str | None = None
    ) -> None:
        tasks.append(((x, y), op, value, item, arg))

    for x, y, tile in animals:
        cost, first, interval, cap, product, _ = ANIMALS[tile["animal"]]
        age = day - tile["placed_day"]
        next_production = (
            day + max(1, first - age) if age < first else day + interval - (age - first) % interval
        )
        useful = next_production <= 29 or tile["yield_units"] > 0
        if not tile["fed_today"] and useful:
            task(
                x,
                y,
                "FEED",
                p["deadline_boost"]
                if tile["consecutive_unfed"] and hour >= 15
                else p["feed_priority"],
                "WHEAT",
            )
        harvest_due = (
            not p["batch_harvest"]
            or tile["yield_units"] >= cap
            or day == 29
            or (next_production == day + 1 and tile["yield_units"] + interval + 1 > cap)
            or farm["money"] < 1000
        )
        if tile["yield_units"] and harvest_due:
            urgent = tile["yield_units"] >= cap - 1 or day == 29
            task(x, y, "HARVEST", 120 if urgent else 45 + tile["yield_units"] * 5)
        if not tile["cared_today"] and tile["fed_today"] and useful and p["care"]:
            task(x, y, "CARE", 60)
        if tile["fertilizer_available"] and day < 29:
            task(x, y, "COLLECT_FERTILIZER", 18 if fert_price < 20 else 40)

    for x, y, tile in plants:
        crop = tile["crop"]
        _, first, last, interval, cap = CROPS[crop]
        age = day - tile["planted_day"]
        yield_units = tile["yield_units"]
        expiry = tile["max_lifespan_step"]
        ripe = age >= first and yield_units > 0
        terminal = day == 29
        growth = (
            (last + 1) // 2 <= age <= last
            if not interval
            else (
                age + 1 >= first
                and (age + 1 - first) % interval == 0
                and (age + 1 - first) // interval < cap
            )
        )
        exhausted = interval and age >= first + (cap - 1) * interval and not yield_units
        if exhausted:
            if day < 27:
                task(x, y, "DIG", 30)
            continue
        if not tile["watered_today"] and not terminal and (tile["consecutive_unwatered"] or growth):
            task(
                x,
                y,
                "WATER",
                p["deadline_boost"]
                if tile["consecutive_unwatered"] and hour >= 15
                else 115
                if tile["consecutive_unwatered"]
                else 65,
            )
        if ripe:
            desired_yield = 2 if interval else min(cap, 1 + (last - (last + 1) // 2 + 1))
            if (
                yield_units >= desired_yield
                or terminal
                or (expiry >= 0 and obs["step"] + 24 >= expiry)
            ):
                task(
                    x,
                    y,
                    "HARVEST",
                    125 if terminal or (expiry >= 0 and obs["step"] + 4 >= expiry) else 70,
                )
        if (
            p["fertilize"]
            and growth
            and not terminal
            and tile["fertilized_until_day"] < day
            and forecast[crop] > fert_price * 0.7 + 10
        ):
            task(x, y, "FERTILIZE", 80 if interval else 72, "FERTILIZER")

    available_animals = [a for a in ANIMALS for _ in range(stock[a])]
    free_cells = sorted(
        [
            (x, y, t)
            for x, y, t in cells
            if t is None
            or (
                isinstance(t, dict)
                and t.get("kind") in ("WEED", "COOP", "PASTURE")
                and "animal" not in t
            )
        ],
        key=lambda z: (min(distance(z[:2], s) for s in shed_tiles), z[1], z[0]),
    )
    animal_sites = {}
    for x, y, tile in free_cells:
        if not available_animals:
            break
        animal = available_animals.pop(0)
        animal_sites[(x, y)] = animal
        kind = ANIMALS[animal][5]
        if tile is None:
            task(x, y, "BUILD_" + kind, 90)
        elif tile.get("kind") == kind:
            task(x, y, "PLACE", 100, animal, animal)
        else:
            task(x, y, "DIG", 85)

    seed_orders: Counter[str] = Counter()
    room = max(0, p["crop_tiles"] - len(plants))
    planned = Counter(crops)
    for x, y, tile in free_cells:
        if (x, y) in animal_sites or room <= 0 or day >= 28:
            continue
        use_fert = p["fertilize"] and fert_price < 70
        values = {
            crop: p["crop_bias"].get(crop, 1)
            * crop_value(
                crop, day, forecast[crop] / (1 + planned[crop] * 0.025), fert_price, use_fert
            )
            for crop in CROPS
        }
        if planned["WHEAT"] < p["feed_grown"] and animals:
            values["WHEAT"] *= 2
        crop = max(values, key=lambda c: values[c])
        if values[crop] <= 0:
            continue
        if seeds.get(crop, 0) > 0:
            if tile is None:
                task(x, y, "PLANT", 42, arg=crop)
            else:
                task(x, y, "DIG", 35)
        elif cash > CROPS[crop][0] + 250 and seed_orders[crop] < 4:
            seed_orders[crop] += 1
            cash -= CROPS[crop][0]
        planned[crop] += 1
        room -= 1
    for crop, amount in seed_orders.items():
        market.append(["BUY_SEED", crop, amount])
    fert_tasks = sum(t[3] == "FERTILIZER" for t in tasks)
    need_fert = min(12, max(0, fert_tasks - stock["FERTILIZER"]))
    if need_fert and cash > need_fert * (fert_price + 1) + 200 and fert_price < 100:
        market.append(["BUY_PRODUCT", "FERTILIZER", need_fert])

    actions: list[list[Any]] = [["PASS"] for _ in positions]
    claimed = set()
    fetches: Counter[str] = Counter()
    demand_inputs = Counter(t[3] for t in tasks if t[3])
    matched: dict[int, tuple[int, int]] = {}
    if p["matching"]:
        destinations = list(dict.fromkeys(t[0] for t in tasks))
        columns = {target: c for c, target in enumerate(destinations)}
        matrix = [[0.0] * (len(destinations) + len(positions)) for _ in positions]
        for i, pos in enumerate(positions):
            home = min(shed_tiles, key=lambda s: distance(pos, s))
            for target, op, value, required_item, arg in tasks:
                if op == "PLANT" and seeds.get(arg, 0) <= 0:
                    continue
                travel = distance(pos, target) + 1
                if required_item and not inventories[i].get(required_item, 0):
                    if not shed.get(required_item, 0):
                        continue
                    travel = distance(pos, home) + distance(home, target) + 2
                c = columns[target]
                matrix[i][c] = min(matrix[i][c], -value / (travel + 1.5))
        matched = {
            i: destinations[c]
            for i, c in enumerate(minimum_assignment(matrix))
            if c < len(destinations) and matrix[i][c] < 0
        }

    # Workers already carrying scarce inputs are assigned first; ties are fixed.
    def local_value(i: int) -> float:
        return max(
            (
                value
                for target, _, value, item, _ in tasks
                if positions[i] == target and (item is None or inventories[i].get(item, 0))
            ),
            default=0,
        )

    order = sorted(
        range(len(positions)), key=lambda i: (-local_value(i), -sum(inventories[i].values()), i)
    )
    for i in order:
        pos, inv = positions[i], inventories[i]
        home = min(shed_tiles, key=lambda s: distance(pos, s))
        home_dist = distance(pos, home)
        load = sum(
            n
            for item, n in inv.items()
            if item in BASE
            and not (item == "WHEAT" and feed_need > 0)
            and not (item == "FERTILIZER" and fert_tasks > 0)
        )
        # Last action is hour 22. DROP then SELL can execute in that same turn.
        end_return = day == 29 and load and hour + home_dist >= 21
        if (
            load
            and ((pos in shed_tiles and load >= 3) or load >= p["return_load"] or end_return)
            and sum(shed.values()) + sum(inv.values()) <= cfg.get("shedCapacity", 100)
        ):
            actions[i] = ["DROP"] if home_dist == 0 else move(pos, home)
            if home_dist == 0:
                for item, n in inv.items():
                    shed[item] = shed.get(item, 0) + n
                    if day == 29 and item in BASE:
                        market.insert(0, ["SELL", item, n])
            continue
        best = None
        for target, op, value, required, arg in tasks:
            if p["matching"] and matched.get(i) != target:
                continue
            if target in claimed:
                continue
            dist = distance(pos, target)
            if hour + dist > 22 and day == 29:
                continue
            if (
                day == 29
                and op == "HARVEST"
                and hour + dist + min(distance(target, s) for s in shed_tiles) + 1 > 22
            ):
                continue
            if op == "PLANT" and seeds.get(arg, 0) <= 0:
                continue
            fetching = required is not None and inv.get(required, 0) <= 0
            if fetching and required is not None:
                if shed.get(required, 0) <= 0 or fetches[required] >= max(
                    1, math.ceil(demand_inputs[required] / 3)
                ):
                    continue
                cost = home_dist + 2 + distance(home, target)
            else:
                cost = dist + 1
            score = value / (cost + 1.5)
            if best is None or score > best[0]:
                best = (score, target, op, required, arg, fetching)
        if best:
            _, target, op, required, arg, fetching = best
            claimed.add(target)
            if fetching and required is not None:
                fetches[required] += 1
                amount = min(
                    shed[required], 3 if required == "WHEAT" else 4, demand_inputs[required]
                )
                if required in ANIMALS:
                    amount = 1
                if home_dist == 0:
                    actions[i] = ["PICKUP", required, amount]
                    shed[required] -= amount
                else:
                    actions[i] = move(pos, home)
            elif pos != target:
                actions[i] = move(pos, target)
            else:
                actions[i] = [op, arg] if arg else [op]
                if op == "PLANT":
                    seeds[arg] -= 1
        elif load and home_dist:
            actions[i] = move(pos, home)
        elif load:
            actions[i] = ["DROP"]
    return {
        "farmer": actions[0],
        "hands": actions[1:],
        "market": market[: cfg.get("maxMarketOrdersPerTurn", 10)],
    }
