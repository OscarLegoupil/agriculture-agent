"""Finite-season investment policy and coordinated value-per-action scheduling.

Self-contained deployment module. Constants follow kaggle-environments 1.32.7.
"""

from __future__ import annotations

import math
import sys
import time
from collections import Counter
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
    "hands": 12,
    "quadrants": 3,
    "cows": 10,
    "sheep": 4,
    "geese": 0,
    "crop_tiles": 50,
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


PRICE_PARAMETERS = {
    "WHEAT": (25, 400, "sqrt", 0.8, "log", 0.2),
    "CARROT": (35, 450, "hinge", 1.0, "sqrt", 0.7),
    "TOMATO": (60, 200, "hinge", 0.4, "sqrt", 0.6),
    "STRAWBERRY": (120, 100, "sqrt", 0.7, "linear", 1.6),
    "MELON": (250, 300, "log", 0.2, "sq", 3.6),
    "EGG": (50, 332, "hinge", 0.4, "log", 0.2),
    "MILK": (160, 122, "sqrt", 0.6, "linear", 1.6),
    "WOOL": (200, 105, "log", 0.2, "sq", 3.2),
    "FERTILIZER": (100, 200, "linear", 0.4, "linear", 0.4),
}


def default_price_parameters() -> dict[str, dict[str, Any]]:
    return {
        item: dict(
            zip(
                ("base", "T", "below_func", "below_target", "above_func", "above_target"),
                values,
                strict=True,
            ),
            I0=10000,
        )
        for item, values in PRICE_PARAMETERS.items()
    }


def price_shape(kind: str, amount: float, scale: float) -> float:
    amount = max(0.0, amount)
    if kind == "sqrt":
        return math.sqrt(amount)
    if kind == "sq":
        return amount**2
    if kind in ("log", "log10"):
        return math.log1p(amount) if kind == "log" else math.log10(1 + amount)
    if kind == "hinge":
        fraction = amount / scale if scale > 0 else amount
        return fraction + 8 * max(0, fraction - 1) ** 2 if scale > 0 else fraction
    return amount


def inventory_quote(inventory: float, spec: dict[str, Any]) -> int:
    shortage = inventory < spec["I0"]
    side = "below" if shortage else "above"
    scale = spec["T"]
    amplitude = spec[side + "_target"] * spec["base"]
    movement = amplitude * price_shape(spec[side + "_func"], abs(inventory - spec["I0"]), scale)
    movement /= price_shape(spec[side + "_func"], scale, scale)
    quote: int = max(1, round(spec["base"] + (movement if shortage else -movement)))
    return quote


def forecast_inventory(
    obs: dict[str, Any],
    crop_specs: dict[str, Any],
    animal_specs: dict[str, Any],
    shops: dict[str, tuple[str, ...]],
) -> tuple[dict[str, float], dict[str, list[int]]]:
    day = obs["day"]
    market = obs["market"]
    parameters = market.get("params") or default_price_parameters()
    inventory = dict(market["inventory"])
    arrivals = [{item: 0.0 for item in inventory} for _ in range(30)]
    animals = 0
    for farm in obs["farms"]:
        for row in farm["tiles"]:
            for tile in row:
                if not isinstance(tile, dict):
                    continue
                if "animal" in tile:
                    animals += 1
                    _, first, interval, cap, item, _ = animal_specs[tile["animal"]]
                    if day < 29:
                        arrivals[day + 1][item] += tile["yield_units"]
                    for future in range(day + 1, 30):
                        age = future - tile["placed_day"]
                        if age >= first and (age - first) % interval == 0:
                            # Imperfect future care/collection is a scenario assumption.
                            arrivals[future][item] += min(cap, 1 + 0.8 * interval)
                elif tile.get("kind") == "PLANT":
                    item = tile["crop"]
                    _, first, last, interval, cap = crop_specs[item]
                    age = day - tile["planted_day"]
                    if interval:
                        if day < 29:
                            arrivals[day + 1][item] += tile["yield_units"]
                        for event in range(first, first + cap * interval, interval):
                            future = tile["planted_day"] + event
                            if day < future < 30:
                                arrivals[future][item] += 1.5
                    else:
                        target = max(day + 1, tile["planted_day"] + max(first, last - 1))
                        if target < 30:
                            watering_days = max(0, target - day)
                            arrivals[target][item] += min(cap, tile["yield_units"] + watering_days)
    traces: dict[str, list[int]] = {item: [] for item in inventory}
    initial_shops = obs["town"]["unlocked_shops"]
    for future in range(day + 1, 30):
        demand = {item: (0.0 if item == "FERTILIZER" else 1.0) for item in inventory}
        for shop in initial_shops:
            products = shops[shop]
            for item in products:
                demand[item] += 12 if len(products) == 1 else 6
        extra = min(8 - len(initial_shops), future // 3 - day // 3)
        for products in shops.values():
            for item in products:
                demand[item] += max(0, extra) * (12 if len(products) == 1 else 6) / len(shops)
        demand["WHEAT"] += animals
        arrivals[future]["FERTILIZER"] += animals * 0.5
        for item in inventory:
            inventory[item] += arrivals[future][item] - demand[item]
            traces[item].append(inventory_quote(inventory[item], parameters[item]))
    first_sale = {item: spec[1] for item, spec in crop_specs.items()}
    first_sale.update({spec[4]: spec[1] for spec in animal_specs.values()})
    first_sale["FERTILIZER"] = 1
    forecasts: dict[str, float] = {}
    for item, values in traces.items():
        if not values:
            forecasts[item] = market["prices"][item]
            continue
        start = min(len(values) - 1, first_sale[item] - 1)
        window = values[start : start + 7]
        forecasts[item] = 0.5 * market["prices"][item] + 0.5 * sum(window) / len(window)
    return forecasts, traces


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
    shed_room = max(0, cfg.get("shedCapacity", 100) - sum(shed.values()))
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
        if item == "FERTILIZER" and p["fertilize"] and day < 29 and cash >= 1000:
            applications = 0
            for _, _, plant in plants:
                _, first, _, interval, cap = CROPS[plant["crop"]]
                if not interval or prices[plant["crop"]] <= fert_price * 0.7 + 10:
                    continue
                first_day = plant["planted_day"] + first
                event = first_day + max(0, math.ceil((day + 1 - first_day) / interval)) * interval
                last_day = first_day + (cap - 1) * interval
                if (
                    event <= min(day + 3, 29, last_day)
                    and plant["fertilized_until_day"] < event - 1
                ):
                    applications += 1
            reserve = max(0, min(12, applications) - carried[item])
        quantity = max(0, shed.get(item, 0) - reserve)
        if sum(shed.values()) < 70 and day < 29:
            quantity = min(quantity, p["sell_batch"])
        if quantity:
            market.append(["SELL", item, quantity])
            # Conservative working capital: do not spend unexecuted sale quotes.

    forecast, _ = forecast_inventory(obs, CROPS, ANIMALS, SHOPS)

    # Investment is bounded by remaining production events and cash. Asset ages
    # come directly from observations and survive every daily planning checkpoint.
    desired = dict.fromkeys(ANIMALS, 18)
    if day < 8:
        desired = dict(COW=2, SHEEP=2, GOOSE=0)
    purchase = None
    if (
        day <= p["animal_stop"]
        and sum(stock[a] for a in ANIMALS) < 2
        and len(animals) + sum(stock[a] for a in ANIMALS) < 18
    ):
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
    workload = max(48 if day < 2 else 0, len(plants) * 1.4 + len(animals) * 4.5)
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
    buy_feed = min(buy_feed, max(0, int((cash - 20) // (prices["WHEAT"] + 1))))
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
        if cash > cost + max(300, feed_need * prices["WHEAT"] + 150):
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
            task(x, y, "COLLECT_FERTILIZER", max(1, fert_price))

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
        # An annual crop gains immediately on WATER. Preserve the last increment
        # only when a worker can still harvest and, on the final day, deliver.
        approach = min(distance(pos, (x, y)) for pos in positions)
        liquidation = min(distance((x, y), home) for home in shed_tiles) + 1 if terminal else 0
        remaining = (23 if terminal else 24) - hour
        if expiry >= 0:
            remaining = min(remaining, expiry - obs["step"])
        water_before_harvest = (
            ripe
            and not interval
            and growth
            and not tile["watered_today"]
            and yield_units < cap
            and approach + 2 + liquidation <= remaining
        )
        exhausted = interval and age >= first + (cap - 1) * interval and not yield_units
        if exhausted:
            if day < 27:
                task(x, y, "DIG", 30)
            continue
        if water_before_harvest or (
            not tile["watered_today"] and not terminal and (tile["consecutive_unwatered"] or growth)
        ):
            task(
                x,
                y,
                "WATER",
                140
                if water_before_harvest
                else (
                    p["deadline_boost"]
                    if tile["consecutive_unwatered"] and hour >= 15
                    else 115
                    if tile["consecutive_unwatered"]
                    else 65
                ),
            )
        if ripe and not water_before_harvest:
            desired_yield = 2 if interval else min(cap, 1 + (last - (last + 1) // 2 + 1))
            if (
                yield_units >= desired_yield
                or (crop == "WHEAT" and (cash < 600 or stock["WHEAT"] < feed_need))
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
            and interval > 0
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
    for x, y, free_tile in free_cells:
        if not available_animals:
            break
        animal = available_animals.pop(0)
        animal_sites[(x, y)] = animal
        kind = ANIMALS[animal][5]
        if free_tile is None:
            task(x, y, "BUILD_" + kind, 90)
        elif free_tile.get("kind") == kind:
            task(x, y, "PLACE", 100, animal, animal)
        else:
            task(x, y, "DIG", 85)

    seed_orders: Counter[str] = Counter()
    room = max(0, p["crop_tiles"] - len(plants))
    planned = Counter(crops)
    for x, y, free_tile in free_cells:
        if (x, y) in animal_sites or room <= 0 or day >= 28:
            continue
        use_fert = p["fertilize"] and fert_price < 70
        values = {
            crop: p["crop_bias"].get(crop, 1)
            * crop_value(
                crop,
                day,
                forecast[crop] / (1 + planned[crop] * 0.025),
                fert_price,
                use_fert and CROPS[crop][3] > 0,
            )
            for crop in CROPS
        }
        if planned["WHEAT"] < p["feed_grown"] and animals:
            values["WHEAT"] *= 2
        # Short crops bridge the first long cohort's startup costs.
        # Later recurring cohorts must arrive early enough to repay before liquidation.
        if day < 15:
            cohort_crop = "WHEAT" if planned["WHEAT"] < 7 else "MELON" if day < 3 else "STRAWBERRY"
            current_value = crop_value(
                cohort_crop,
                day,
                prices[cohort_crop],
                fert_price,
                use_fert and CROPS[cohort_crop][3] > 0,
            )
            if current_value > 0:
                values[cohort_crop] = max(1, max(values.values()) + 1)
        crop = max(values, key=lambda c: values[c])
        if values[crop] <= 0:
            continue
        if seeds.get(crop, 0) > 0:
            if free_tile is None:
                if hour < 23:
                    task(x, y, "PLANT", 42, arg=crop)
            else:
                task(x, y, "DIG", 35)
        elif cash > CROPS[crop][0] + (30 if day < 2 else 200) and seed_orders[crop] < 4:
            seed_orders[crop] += 1
            cash -= CROPS[crop][0]
        planned[crop] += 1
        room -= 1
    for crop, amount in seed_orders.items():
        market.append(["BUY_SEED", crop, amount])
    fert_tasks = sum(t[3] == "FERTILIZER" for t in tasks)
    need_fert = max(0, min(12, fert_tasks) - stock["FERTILIZER"])
    if need_fert and cash > need_fert * (fert_price + 1) + 200 and fert_price < 100:
        market.append(["BUY_PRODUCT", "FERTILIZER", need_fert])

    actions: list[list[Any]] = [["PASS"] for _ in positions]
    claimed = set()
    fetches: Counter[str] = Counter()
    demand_inputs = Counter(t[3] for t in tasks if t[3])
    # Reserve last-departure feed routes before ordinary task matching or DROP.
    # Feasibility includes acquiring feed and the action after arriving at the animal.
    deadline_actions = {}
    if day < 29:
        pending = {
            target
            for target, op, _, _, _ in tasks
            if op == "FEED" and board[target[1]][target[0]]["consecutive_unfed"] > 0
        }
        all_carried = sum(sum(inv.values()) for inv in inventories)
        safe_nightly = sum(shed.values()) + all_carried <= cfg.get("shedCapacity", 100)
        while pending:
            candidates = []
            for target in pending:
                routes = []
                for i, pos in enumerate(positions):
                    if i in deadline_actions:
                        continue
                    inv = inventories[i]
                    sale_cargo = sum(
                        n
                        for item, n in inv.items()
                        if item in BASE and item not in ("WHEAT", "FERTILIZER")
                    )
                    if sale_cargo and (farm["money"] < 1000 or not safe_nightly):
                        continue
                    fetching = not inv.get("WHEAT", 0)
                    home = min(shed_tiles, key=lambda s: distance(pos, s) + distance(s, target))
                    if fetching:
                        if shed.get("WHEAT", 0) <= 0:
                            continue
                        cost = distance(pos, home) + 1 + distance(home, target) + 1
                    else:
                        cost = distance(pos, target) + 1
                    slack = 24 - hour - cost
                    if slack >= 0:
                        routes.append((cost, i, home, fetching, slack))
                if routes:
                    route = min(routes)
                    if route[-1] <= 3:
                        candidates.append((route[-1], target, route))
            if not candidates:
                break
            _, target, (_, i, home, fetching, _) = min(candidates)
            pos = positions[i]
            if fetching:
                # Reserve one shared unit even while the assigned worker walks.
                shed["WHEAT"] -= 1
                fetches["WHEAT"] += 1
                action = ["PICKUP", "WHEAT", 1] if pos == home else move(pos, home)
            else:
                action = ["FEED"] if pos == target else move(pos, target)
            deadline_actions[i] = action
            actions[i] = action
            claimed.add(target)
            pending.remove(target)
    matched: dict[int, tuple[int, int]] = {}
    if p["matching"]:
        destinations = list(dict.fromkeys(t[0] for t in tasks))
        columns = {target: c for c, target in enumerate(destinations)}
        matrix = [[0.0] * (len(destinations) + len(positions)) for _ in positions]
        for i, pos in enumerate(positions):
            if i in deadline_actions:
                continue
            home = min(shed_tiles, key=lambda s: distance(pos, s))
            for target, op, value, required_item, arg in tasks:
                if target in claimed:
                    continue
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
        if i in deadline_actions:
            continue
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
            and sum(inv.values()) <= shed_room
        ):
            actions[i] = ["DROP"] if home_dist == 0 else move(pos, home)
            if home_dist == 0:
                shed_room -= sum(inv.values())
                for item, n in inv.items():
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
        elif load and sum(inv.values()) <= shed_room:
            actions[i] = ["DROP"]
            shed_room -= sum(inv.values())
    # At the final action, coalesce repeated sales before the order limit.
    # Preserve first-seen product order and never move a sale across a buy.
    if day == 29 and hour == 22 and len(market) > cfg.get("maxMarketOrdersPerTurn", 10):
        consolidated: list[list[Any]] = []
        sale_positions: dict[str, int] = {}
        for sale_order in market:
            if sale_order[0] == "SELL":
                item = sale_order[1]
                if item in sale_positions:
                    consolidated[sale_positions[item]][2] += sale_order[2]
                else:
                    sale_positions[item] = len(consolidated)
                    consolidated.append(list(sale_order))
            else:
                sale_positions.clear()
                consolidated.append(sale_order)
        market = consolidated
    return {
        "farmer": actions[0],
        "hands": actions[1:],
        "market": market[: cfg.get("maxMarketOrdersPerTurn", 10)],
    }
