"""Whole-farm daily route insertion with economic bundles and shared reservations."""

from __future__ import annotations

import gzip
import hashlib
import inspect
import sys
import time
from collections import Counter
from pathlib import Path

from scripts.phase4_delivery import immediate_delivery_sales

from kaggriculture.agent.competitive import ANIMALS, BASE, CROPS, distance, move

INCUMBENT = "64fe323936dc9494add413eb956b0294658a88efe28572332c94676c68a09325"
_DAILY_ROUTES = {}
_DAILY_ROUTE_STATS = Counter()


def daily_routes(
    obs,
    cfg,
    positions,
    inventories,
    shed,
    seeds,
    tasks,
    access,
    animal_sites,
    forecast,
    target_hands,
):
    """Insert local service bundles while retaining a feasible daily fleet plan.

    Required irrigation and valuable production/escape feeding are allocated
    first. Optional work is inserted only when full pickup and execution costs
    preserve the worker's already-reserved obligations. No future realized
    demand, reference action tapes or private opponent state is used.
    """
    player, day, hour, step = obs["player"], obs["day"], obs["hour"], obs["step"]
    farm, board = obs["farms"][player], obs["farms"][player]["tiles"]
    prices = obs["market"]["prices"]
    hire_runway, first, second = 121, 1, 1
    for index in range(target_hands):
        if index >= len(farm["hands"]):
            hire_runway += first
        first, second = second, first + second
    liquidity_needed = (
        len(farm["hands"]) < target_hands and farm["money"] < hire_runway and hour < 8
    )
    end = 23 if day == 29 else 24
    capacity = cfg.get("shedCapacity", 100)
    deadline = time.perf_counter() + 0.065
    state = _DAILY_ROUTES.get(player)
    if (
        not state
        or state["day"] != day
        or step not in (state["step"], state["step"] + 1)
        or step == 0
    ):
        state = {"day": day, "step": step, "plans": {}}
        _DAILY_ROUTES[player] = state
    state["step"] = step
    plans = state["plans"]
    observation_key = (step, repr(farm), repr(obs["private"]), repr(prices), capacity)
    if state.get("observation_key") == observation_key:
        cached_actions, cached_claimed, cached_shed, cached_seeds = state["decision"]
        shed.update(cached_shed)
        seeds.update(cached_seeds)
        return {worker: list(action) for worker, action in cached_actions.items()}, set(
            cached_claimed
        )

    def tile_at(target):
        return board[target[1]][target[0]]

    def animal_value(tile):
        _, first, interval, cap, product, _ = ANIMALS[tile["animal"]]
        first_day = tile["placed_day"] + first
        next_day = first_day if day < first_day else day + interval - (day - first_day) % interval
        events = max(0, 1 + (29 - next_day) // interval)
        # Residual production option; purchase cost is sunk and has no salvage.
        residual = events * min(cap, interval + 1) * forecast[product]
        residual += max(0, 28 - day) * max(0, prices["FERTILIZER"] - 4)
        residual -= max(0, 28 - day) * prices["WHEAT"]
        return next_day, product, max(0, residual)

    def crop_value_left(tile):
        crop = tile["crop"]
        _, first, last, interval, cap = CROPS[crop]
        if interval:
            events = sum(
                day < tile["planted_day"] + first + index * interval <= 29 for index in range(cap)
            )
            units = tile["yield_units"] + events * 1.5
        else:
            growth = sum(
                day < future <= min(tile["planted_day"] + last, 29)
                for future in range(
                    tile["planted_day"] + (last + 1) // 2, tile["planted_day"] + last + 1
                )
            )
            units = min(cap, tile["yield_units"] + growth)
            if tile["planted_day"] + first > 29:
                units = 0
        return units * forecast[crop]

    def requirements(operations):
        inputs, seed_use = Counter(), Counter()
        for _, op, arg in operations:
            if op == "FEED":
                inputs["WHEAT"] += 1
            elif op == "FERTILIZE":
                inputs["FERTILIZER"] += 1
            elif op == "PLACE":
                inputs[arg] += 1
            elif op == "PLANT":
                seed_use[arg] += 1
        return inputs, seed_use

    def route_cost(worker, operations):
        _, seed_use = requirements(operations)
        carried = Counter(inventories[worker])
        missing, watered, fertilized = Counter(), set(), set()
        for target, op, arg in operations:
            item = (
                "WHEAT"
                if op == "FEED"
                else "FERTILIZER"
                if op == "FERTILIZE"
                else arg
                if op == "PLACE"
                else None
            )
            if item:
                if carried[item] < 1:
                    missing[item] += 1
                    carried[item] += 1
                carried[item] -= 1
            if op == "COLLECT_FERTILIZER":
                carried["FERTILIZER"] += 1
            elif op == "FERTILIZE":
                fertilized.add(target)
            elif op == "WATER":
                watered.add(target)
            elif op == "HARVEST":
                tile = tile_at(target)
                if (
                    isinstance(tile, dict)
                    and tile.get("kind") == "PLANT"
                    and tile["crop"] == "WHEAT"
                ):
                    units = tile["yield_units"]
                    if (
                        target in watered
                        and not tile["watered_today"]
                        and 2 <= day - tile["planted_day"] <= 4
                    ):
                        units = min(
                            6,
                            units
                            + (
                                2
                                if target in fertilized or tile["fertilized_until_day"] >= day
                                else 1
                            ),
                        )
                    carried["WHEAT"] += units
        pos = positions[worker]
        cost, home = 0, None
        if missing:
            home = min(
                access,
                key=lambda depot: (distance(pos, depot) + distance(depot, operations[0][0]), depot),
            )
            cost += distance(pos, home) + len(missing)
            pos = home
        for target, _, _ in operations:
            cost += distance(pos, target) + 1
            pos = target
        return cost, missing, seed_use, home

    def one_delivery(worker, operations):
        """A bulk delivery terminates a route; never discard later input cargo."""
        deliver = any(op == "DROP" for _, op, _ in operations)
        plain = [operation for operation in operations if operation[1] != "DROP"]
        collecting = any(op in ("HARVEST", "COLLECT_FERTILIZER") for _, op, _ in plain)
        melons = any(
            op == "HARVEST"
            and isinstance(tile_at(target), dict)
            and tile_at(target).get("crop") == "MELON"
            for target, op, _ in plain
        )
        deliver = (
            deliver
            or bool(inventories[worker].get("MELON", 0))
            or melons
            or (collecting and (day == 29 or farm["money"] < 500))
        )
        if deliver:
            final = plain[-1][0] if plain else positions[worker]
            home = min(access, key=lambda depot: (distance(final, depot), depot))
            plain.append((home, "DROP", None))
        return plain

    def pending(operation, expected, creating=False):
        target, op, _arg = operation
        tile = tile_at(target)
        kind = tile.get("kind") if isinstance(tile, dict) else None
        if op == "DROP":
            return True
        if op.startswith("BUILD_"):
            return tile is None
        if op == "DIG":
            return tile is not None and not (isinstance(tile, dict) and "animal" in tile)
        if op == "PLANT":
            return tile is None
        if op == "PLACE":
            return not (isinstance(tile, dict) and "animal" in tile)
        if expected and expected[0] == "PLANT":
            if tile is None:
                return creating and op == "WATER"
            if kind != "PLANT" or (tile["crop"], tile["planted_day"]) != expected[1:]:
                return False
        elif expected and expected[0] == "ANIMAL":
            if not isinstance(tile, dict) or "animal" not in tile:
                return creating and op in ("FEED", "CARE")
            if (tile["animal"], tile["placed_day"]) != expected[1:]:
                return False
        if op == "WATER":
            return kind == "PLANT" and not tile["watered_today"]
        if op == "FERTILIZE":
            return kind == "PLANT" and tile["fertilized_until_day"] < day
        if op == "HARVEST":
            return isinstance(tile, dict) and tile.get("yield_units", 0) > 0
        if not isinstance(tile, dict) or "animal" not in tile:
            return False
        return {
            "FEED": not tile["fed_today"],
            "CARE": not tile["cared_today"],
            "COLLECT_FERTILIZER": tile["fertilizer_available"],
        }.get(op, False)

    for worker in list(plans):
        plan = plans[worker]
        if worker >= len(positions):
            del plans[worker]
            continue
        creating = {target for target, op, _ in plan["ops"] if op in ("PLANT", "PLACE")}
        operations, waiting = [], set()
        for operation in plan["ops"]:
            target = operation[0]
            # Later operations on this tile are conditional on its first
            # unfinished operation. A still-present weed does not invalidate
            # BUILD/PLANT behind DIG, nor zero yield HARVEST behind WATER.
            if target in waiting or pending(
                operation, plan["expected"].get(target), target in creating
            ):
                operations.append(operation)
                waiting.add(target)
        if operations and operations[0][1] == "DROP" and not inventories[worker]:
            operations = []
        if not operations or hour + route_cost(worker, operations)[0] > end:
            del plans[worker]
        else:
            plan["ops"] = operations
        liquid_cargo = sum(
            amount * prices.get(item, 0)
            for item, amount in inventories[worker].items()
            if item in BASE and item != "WHEAT"
        )
        if liquidity_needed and liquid_cargo > 0:
            home = min(access, key=lambda depot: (distance(positions[worker], depot), depot))
            plans[worker] = {"ops": [(home, "DROP", None)], "expected": {}}

    # Claim all inputs for retained routes, including workers walking to depot.
    available, seed_available = Counter(shed), Counter(seeds)
    for worker in sorted(list(plans)):
        _, needed, seed_use, _ = route_cost(worker, plans[worker]["ops"])
        if any(amount > available[item] for item, amount in needed.items()) or any(
            amount > seed_available[item] for item, amount in seed_use.items()
        ):
            _DAILY_ROUTE_STATS["resource_invalidations"] += 1
            del plans[worker]
        else:
            available.subtract(needed)
            seed_available.subtract(seed_use)
    claimed = {target for plan in plans.values() for target, op, _ in plan["ops"] if op != "DROP"}
    grouped = {}
    for target, op, _, _, arg in tasks:
        if target not in claimed:
            grouped.setdefault(target, {})[op] = arg
    if day == 29:
        for y, row in enumerate(board):
            for x, tile in enumerate(row):
                target = (x, y)
                if (
                    target not in claimed
                    and isinstance(tile, dict)
                    and "animal" in tile
                    and tile["fertilizer_available"]
                ):
                    grouped.setdefault(target, {})["COLLECT_FERTILIZER"] = None

    bundles = []
    for target, choices in grouped.items():
        tile = tile_at(target)
        operations, value, required, expected = [], 0.0, False, None
        if isinstance(tile, dict) and "animal" in tile:
            expected = ("ANIMAL", tile["animal"], tile["placed_day"])
            next_day, product, residual = animal_value(tile)
            production_eve = next_day == day + 1
            bonus_day = next_day + ANIMALS[tile["animal"]][2] if production_eve else next_day
            useful_care = bonus_day <= 29
            care_value = forecast[product] if useful_care else 0
            feed_value = (
                tile.get("pending_care_bonus", 0) * prices[product] if production_eve else 0
            )
            if tile["consecutive_unfed"]:
                feed_value += residual + tile["yield_units"] * prices[product]
            if "FEED" in choices and day < 29 and feed_value + care_value > prices["WHEAT"]:
                operations.append((target, "FEED", None))
                value += feed_value + care_value - prices["WHEAT"]
                required = bool(
                    tile["consecutive_unfed"] or (production_eve and feed_value > prices["WHEAT"])
                )
            feeding = tile["fed_today"] or any(op == "FEED" for _, op, _ in operations)
            if "HARVEST" in choices:
                operations.append((target, "HARVEST", None))
                value += tile["yield_units"] * prices[product]
            if feeding and not tile["cared_today"] and useful_care:
                operations.append((target, "CARE", None))
                if tile["fed_today"]:
                    value += care_value
            if "COLLECT_FERTILIZER" in choices:
                operations.append((target, "COLLECT_FERTILIZER", None))
                value += prices["FERTILIZER"]
        elif isinstance(tile, dict) and tile.get("kind") == "PLANT":
            crop = tile["crop"]
            _, first, last, interval, cap = CROPS[crop]
            age = day - tile["planted_day"]
            expected = ("PLANT", crop, tile["planted_day"])
            if "DIG" in choices:
                operations.append((target, "DIG", None))
                value = max(0, forecast["WHEAT"] * 2 - CROPS["WHEAT"][0]) if day <= 26 else 0
            else:
                water = "WATER" in choices
                growth = not interval and (last + 1) // 2 <= age <= last
                event = bool(
                    interval
                    and age + 1 >= first
                    and (age + 1 - first) % interval == 0
                    and (age + 1 - first) // interval < cap
                )
                fertilize = (
                    "FERTILIZE" in choices and event and forecast[crop] > prices["FERTILIZER"] + 4
                )
                if fertilize:
                    operations.append((target, "FERTILIZE", None))
                    value += max(0, forecast[crop] - prices["FERTILIZER"])
                    water = not tile["watered_today"]
                if water:
                    operations.append((target, "WATER", None))
                    required = bool(tile["consecutive_unwatered"] and day < 29)
                    if required:
                        value += crop_value_left(tile)
                    elif growth:
                        value += prices[crop] * (2 if tile["fertilized_until_day"] >= day else 1)
                    elif event and tile["fertilized_until_day"] >= day:
                        value += forecast[crop]
                units_after = tile["yield_units"] + int(water and growth) * (
                    2 if tile["fertilized_until_day"] >= day else 1
                )
                desired = 2 if interval else min(cap, 1 + last - (last + 1) // 2 + 1)
                harvest = "HARVEST" in choices or (
                    water and age >= first and (units_after >= desired or day == 29 or age >= last)
                )
                if harvest:
                    operations.append((target, "HARVEST", None))
                    value += min(cap, units_after) * prices[crop]
        elif "PLANT" in choices or ("DIG" in choices and choices["DIG"] in CROPS):
            crop = choices.get("PLANT") or choices["DIG"]
            _, first, last, interval, cap = CROPS[crop]
            events = max(0, min(cap, 1 + (29 - day - first) // interval)) if interval else 0
            units = (
                events * 1.5
                if interval
                else min(cap, 1 + max(0, min(last, 29 - day) - (last + 1) // 2 + 1))
            )
            if day + first <= 29 and day < 28:
                if tile is not None:
                    operations.append((target, "DIG", None))
                operations.extend(((target, "PLANT", crop), (target, "WATER", None)))
                expected = ("PLANT", crop, day)
                # Seeds already in private stock are sunk. Charge the future
                # maintenance needed to reach these finite-season products.
                service = first / 2 + (events if interval else 1)
                value = max(0, units * forecast[crop] - 4 * service)
        elif target in animal_sites:
            animal = animal_sites[target]
            expected = ("ANIMAL", animal, day)
            if any(op.startswith("BUILD_") for op in choices):
                operations.append((target, "BUILD_" + ANIMALS[animal][5], None))
            elif "DIG" in choices:
                operations.append((target, "DIG", None))
                operations.append((target, "BUILD_" + ANIMALS[animal][5], None))
            operations.append((target, "PLACE", animal))
            next_day, product, residual = animal_value(dict(animal=animal, placed_day=day))
            value = residual
            existing_feed = shed.get("WHEAT", 0) + sum(inv.get("WHEAT", 0) for inv in inventories)
            if existing_feed and next_day <= 29 and prices["WHEAT"] < forecast[product]:
                operations.extend(((target, "FEED", None), (target, "CARE", None)))
                value += forecast[product] - prices["WHEAT"]
        if operations and value > 0:
            liquid = False
            if liquidity_needed:
                collection = [
                    operation
                    for operation in operations
                    if operation[1] in ("HARVEST", "COLLECT_FERTILIZER")
                    and not (operation[1] == "HARVEST" and tile.get("crop") == "WHEAT")
                ]
                if collection:
                    product = ANIMALS[tile["animal"]][4] if "animal" in tile else tile["crop"]
                    receipts = sum(
                        tile.get("yield_units", 0) * prices[product]
                        if op == "HARVEST"
                        else prices["FERTILIZER"]
                        for _, op, _ in collection
                    )
                    if receipts > 0:
                        # Collection has no feed prerequisite. Recover a hire's
                        # cash runway before committing the only worker to a
                        # productive asset whose first sale is many days away.
                        operations, value, required, liquid = collection, receipts, False, True
            bundles.append(
                dict(
                    target=target,
                    ops=operations,
                    value=value,
                    required=required,
                    targets={target},
                    expectations={target: expected},
                    premium=isinstance(tile, dict)
                    and tile.get("crop") == "MELON"
                    and any(op == "HARVEST" for _, op, _ in operations),
                    liquid=liquid,
                    commissioning=any(op in ("PLANT", "PLACE") for _, op, _ in operations),
                )
            )

    # Required bundles precede optional investment/collection. Within each tier,
    # insertion minimizes extra travel rather than redispatching every step.
    by_target = {bundle["target"]: bundle for bundle in bundles}
    exhausted = False
    examined = 0
    while bundles:
        if examined >= 512:
            break
        if time.perf_counter() >= deadline:
            exhausted = True
            break
        anchors = [
            *positions,
            *(target for plan in plans.values() for target, op, _ in plan["ops"] if op != "DROP"),
        ]
        bundle = min(
            bundles,
            key=lambda candidate: (
                0
                if candidate["liquid"]
                else 1
                if candidate["premium"]
                else 2
                if candidate["required"]
                else 3,
                -candidate["value"]
                / (
                    len(candidate["ops"])
                    + min(distance(candidate["target"], anchor) for anchor in anchors)
                ),
                candidate["target"],
            ),
        )
        bundles.remove(bundle)
        best = None
        variants = [bundle]
        if any(op == "FEED" for _, op, _ in bundle["ops"]):
            feed_sources = []
            for target, source in by_target.items():
                tile = tile_at(target)
                if (
                    target not in claimed
                    and target != bundle["target"]
                    and isinstance(tile, dict)
                    and tile.get("crop") == "WHEAT"
                    and any(op == "HARVEST" for _, op, _ in source["ops"])
                ):
                    feed_sources.append(source)
            feed_sources.sort(
                key=lambda source: (distance(source["target"], bundle["target"]), source["target"])
            )
            for source in feed_sources[:3]:
                combined = dict(bundle)
                combined.update(
                    ops=[*source["ops"], *bundle["ops"]],
                    value=source["value"] + bundle["value"],
                    targets=source["targets"] | bundle["targets"],
                    expectations=source["expectations"] | bundle["expectations"],
                )
                variants.append(combined)
        route_details = {worker: route_cost(worker, plan["ops"]) for worker, plan in plans.items()}
        for worker in range(len(positions)):
            old = plans.get(worker, {"ops": [], "expected": {}})
            old_ops = old["ops"]
            if liquidity_needed and any(op == "DROP" for _, op, _ in old_ops):
                continue
            if inventories[worker].get("MELON", 0) or any(
                op == "HARVEST"
                and isinstance(tile_at(target), dict)
                and tile_at(target).get("crop") == "MELON"
                for target, op, _ in old_ops
            ):
                continue
            liquid_cargo = sum(
                amount * prices.get(item, 0)
                for item, amount in inventories[worker].items()
                if item in BASE and item != "WHEAT"
            )
            if liquidity_needed and liquid_cargo > 0:
                continue
            old_cost, old_need, old_seeds, _ = (
                route_details[worker] if old_ops else (0, Counter(), Counter(), None)
            )
            other_finish = max(
                (details[0] for other, details in route_details.items() if other != worker),
                default=0,
            )
            # Insert only between complete tile visits; service prerequisites
            # cannot be separated by another worker or a later optional task.
            slots = (
                [0]
                + [
                    index
                    for index in range(1, len(old_ops))
                    if old_ops[index - 1][0] != old_ops[index][0]
                ]
                + ([len(old_ops)] if old_ops else [])
            )
            for variant, slot in ((variant, slot) for variant in variants for slot in slots):
                if examined >= 512:
                    break
                if time.perf_counter() >= deadline:
                    exhausted = True
                    break
                examined += 1
                operations = one_delivery(
                    worker, [*old_ops[:slot], *variant["ops"], *old_ops[slot:]]
                )
                melon_index = next(
                    (
                        index
                        for index, (target, op, _) in enumerate(operations)
                        if op == "HARVEST"
                        and isinstance(tile_at(target), dict)
                        and tile_at(target).get("crop") == "MELON"
                    ),
                    None,
                )
                if melon_index is not None and any(
                    op != "DROP" for _, op, _ in operations[melon_index + 1 :]
                ):
                    continue
                cost, need, seed_use, _ = route_cost(worker, operations)
                if hour + cost > end:
                    continue
                if any(amount > available[item] + old_need[item] for item, amount in need.items()):
                    continue
                if any(
                    amount > seed_available[item] + old_seeds[item]
                    for item, amount in seed_use.items()
                ):
                    continue
                # Additional effort must create more than its opportunity cost.
                extra = max(1, cost - old_cost)
                score = variant["value"] / extra
                if not bundle["required"] and score < 4:
                    continue
                # Workers are already hired. Finish the mandatory workload
                # across the fleet before filling individual routes to dusk;
                # otherwise one worker can monopolize crops and their feed.
                rank = (
                    (cost, extra, worker, slot)
                    if bundle["premium"] or bundle["liquid"] or bundle["commissioning"]
                    else (max(cost, other_finish), extra, worker, slot)
                    if bundle["required"]
                    else (-score, cost, worker, slot)
                )
                if best is None or rank < best[0]:
                    best = rank, worker, operations, need, seed_use, old_need, old_seeds, variant
        if best is None:
            if bundle["required"]:
                _DAILY_ROUTE_STATS["unassigned_obligations"] += 1
            continue
        _, worker, operations, need, seed_use, old_need, old_seeds, selected = best
        available.update(old_need)
        available.subtract(need)
        seed_available.update(old_seeds)
        seed_available.subtract(seed_use)
        expected = dict(plans.get(worker, {}).get("expected", {}))
        expected.update(selected["expectations"])
        plans[worker] = {"ops": operations, "expected": expected}
        claimed.update(selected["targets"])
        bundles = [pending for pending in bundles if pending["target"] not in claimed]

    actions = {}
    drop_room = capacity - sum(obs["private"]["shed"].values())
    for worker in sorted(plans):
        operations = plans[worker]["ops"]
        pos = positions[worker]
        _, missing, _, home = route_cost(worker, operations)
        if missing:
            item = sorted(missing, key=lambda item: (item != "WHEAT", item))[0]
            actions[worker] = ["PICKUP", item, missing[item]] if pos == home else move(pos, home)
        else:
            target, op, arg = operations[0]
            if op == "DROP" and sum(inventories[worker].values()) > drop_room:
                # Let the incumbent sell/recover inventory before a safe DROP.
                _DAILY_ROUTE_STATS["blocked_deliveries"] += 1
                actions[worker] = ["PASS"]
            else:
                actions[worker] = (
                    ([op, arg] if arg else [op]) if pos == target else move(pos, target)
                )
                if actions[worker] == ["DROP"]:
                    drop_room -= sum(inventories[worker].values())
        _DAILY_ROUTE_STATS["committed_actions"] += 1
    if exhausted:
        _DAILY_ROUTE_STATS["budget_fallbacks"] += 1
        print("daily_route_budget_fallback", file=sys.stderr)
    if examined >= 512:
        _DAILY_ROUTE_STATS["bounded_searches"] += 1
    _DAILY_ROUTE_STATS["insertion_evaluations"] += examined
    for item in shed:
        shed[item] = max(0, available[item])
    for item in seeds:
        seeds[item] = max(0, seed_available[item])
    state["observation_key"] = observation_key
    state["decision"] = (
        {worker: list(action) for worker, action in actions.items()},
        set(claimed),
        dict(shed),
        dict(seeds),
    )
    return actions, claimed


def build():
    root = Path(__file__).resolve().parents[1]
    raw = gzip.decompress((root / "reports/sources" / f"{INCUMBENT}.py.gz").read_bytes())
    assert hashlib.sha256(raw).hexdigest() == INCUMBENT
    source = raw.decode()
    marker = "    deadline_actions = {}\n    if day < 29:"
    replacement = """    deadline_actions, route_claimed = daily_routes(
        obs, cfg, positions, inventories, shed, seeds, tasks, shed_tiles, animal_sites, forecast,
        target_hands,
    )
    claimed.update(route_claimed)
    for worker, action in deadline_actions.items():
        actions[worker] = action
        if action == ["DROP"]:
            shed_room -= sum(inventories[worker].values())
            if day == 29:
                for item, amount in inventories[worker].items():
                    if item in BASE and amount:
                        market.insert(0, ["SELL", item, amount])
    if day < 29:"""
    assert source.count(marker) == 1
    source = source.replace(marker, replacement)
    source = source.replace(
        'if op == "FEED" and board[target[1]][target[0]]["consecutive_unfed"] > 0',
        'if op == "FEED" and target not in claimed and board[target[1]][target[0]]["consecutive_unfed"] > 0',
    )
    source = source.replace('task(x, y, "DIG", 35)', 'task(x, y, "DIG", 35, arg=crop)')
    helpers = "_DAILY_ROUTES = {}\n_DAILY_ROUTE_STATS = Counter()\n\n" + inspect.getsource(
        daily_routes
    )
    projector = inspect.getsource(immediate_delivery_sales)
    eligible = 'if item not in ("CARROT", "TOMATO", "STRAWBERRY", "MELON", "EGG", "MILK", "WOOL"):'
    assert projector.count(eligible) == 1
    helpers += "\n\n" + projector.replace(eligible, 'if item != "MELON":')
    source = source.replace("def agent(", helpers + "\n\ndef agent(")
    source = source.replace(
        '        "market": market[: cfg.get("maxMarketOrdersPerTurn", 10)],',
        '        "market": immediate_delivery_sales(obs, cfg, actions, market),',
    )
    source = source.replace(
        '"""Pure observation policy: no episode globals or repository imports."""',
        '"""Observation policy with disposable, verified daily fleet routes."""',
    )
    compile(source, "daily_routes_candidate", "exec")
    return source


if __name__ == "__main__":
    print(hashlib.sha256(build().encode()).hexdigest())
