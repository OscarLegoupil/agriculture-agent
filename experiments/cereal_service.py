"""Fertilized wheat cycles on the corrected fleet's existing crop sites.

One age-2 application covers both age-2 and age-3 watering. Five units can then
be harvested at age 3. Admission charges fertilizer at its current sale value;
future prices and perfect recurring reinvestment are not assumed. Renewal uses
the fleet's real shared seed reservations and its complete same-day route cost.
"""

import hashlib
import inspect
import textwrap

from experiments.daily_routes import build as build_fleet
from experiments.wheat_service import wheat_uncommitted_cash

from kaggriculture.agent.competitive import CROPS, default_price_parameters, inventory_quote

FLEET = "9400f9b0cdaa02d268ab9e234779d17013f2facf5f5517698bdfdb04671464b7"


def cereal_fertilizer_worthwhile(obs, tile):
    """Conservative one-grain gain over four-unit, age-4 unfertilized wheat."""
    return (
        tile.get("crop") == "WHEAT"
        and 1 <= obs["day"] - tile["planted_day"] <= 2
        and tile["planted_day"] + 3 <= 29
        and tile["fertilized_until_day"] < tile["planted_day"] + 3
        and obs["market"]["prices"]["WHEAT"] > obs["market"]["prices"]["FERTILIZER"] + 4
    )


def cereal_input_orders(obs, cfg, orders, fertilizer, renewal):
    """Finance small input buffers before the next worker action can use them.

    All incumbent purchases keep their funding priority. Current animal feed is
    also protected by a cash reserve. No pending sale receipt is counted. Failed
    purchases leave no imagined stock in the route planner.
    """
    if obs["day"] < 8 or obs["day"] > 28:
        return orders
    farm = obs["farms"][obs["player"]]
    wheat = [
        tile
        for row in farm["tiles"]
        for tile in row
        if isinstance(tile, dict) and tile.get("crop") == "WHEAT"
    ]
    animals = sum(isinstance(t, dict) and "animal" in t for row in farm["tiles"] for t in row)
    reserve = max(50, animals * obs["market"]["prices"]["WHEAT"])
    result = [list(order) for order in orders]
    limit = cfg.get("maxMarketOrdersPerTurn", 10)
    desired = []
    if renewal and obs["day"] <= 26:
        upcoming = sum(tile["planted_day"] + 3 <= 26 for tile in wheat)
        desired.append(("BUY_SEED", "WHEAT", min(6, upcoming)))
    if fertilizer:
        upcoming = sum(cereal_fertilizer_worthwhile(obs, tile) for tile in wheat)
        desired.append(("BUY_PRODUCT", "FERTILIZER", min(4, upcoming)))
    for operation, item, target in desired:
        private = obs["private"]
        held = (
            private["seeds"].get(item, 0)
            if operation == "BUY_SEED"
            else private["shed"].get(item, 0)
            + sum(inv.get(item, 0) for inv in private["inventories"])
        )
        visible = result[:limit]
        pending = sum(order[2] for order in visible if order[:2] == [operation, item])
        purchase = next((order for order in visible if order[:2] == [operation, item]), None)
        if held + pending >= target or (purchase is None and len(result) >= limit):
            continue
        cash = wheat_uncommitted_cash(obs, cfg, result) - reserve
        quantity = 0
        for amount in range(1, target - held - pending + 1):
            price = (
                CROPS[item][0]
                if operation == "BUY_SEED"
                else inventory_quote(
                    obs["market"]["inventory"][item] - pending - amount,
                    (obs["market"].get("params") or default_price_parameters())[item],
                )
            )
            if amount * price > cash:
                break
            quantity = amount
        if quantity:
            if purchase is None:
                result.append([operation, item, quantity])
            else:
                purchase[2] += quantity
    return result


def cereal_fertilizer_reserve(obs):
    """Keep the funded annual-crop buffer through the incumbent selling pass."""
    if obs["day"] < 8:
        return 0
    farm, private = obs["farms"][obs["player"]], obs["private"]
    upcoming = sum(
        cereal_fertilizer_worthwhile(obs, tile)
        for row in farm["tiles"]
        for tile in row
        if isinstance(tile, dict) and tile.get("kind") == "PLANT"
    )
    return max(
        0,
        min(4, upcoming) - sum(inv.get("FERTILIZER", 0) for inv in private["inventories"]),
    )


def cereal_tasks(obs, tasks, plants, fertilizer):
    """Add only observed annual-wheat opportunities; keep feed rescue available."""
    if not fertilizer or obs["day"] < 8:
        return tasks
    candidates, protected = [], set()
    farm, private = obs["farms"][obs["player"]], obs["private"]
    stock = private["shed"].get("WHEAT", 0) + sum(
        inv.get("WHEAT", 0) for inv in private["inventories"]
    )
    need = sum(
        isinstance(tile, dict) and "animal" in tile and not tile["fed_today"]
        for row in farm["tiles"]
        for tile in row
    )
    feed_financed = (
        stock >= need or farm["money"] > (need - stock) * obs["market"]["prices"]["WHEAT"] + 150
    )
    for x, y, tile in plants:
        if tile["crop"] != "WHEAT" or obs["day"] - tile["planted_day"] != 2:
            continue
        if feed_financed and tile["fertilized_until_day"] >= tile["planted_day"] + 3:
            protected.add((x, y))
        if not tile["watered_today"] and feed_financed and cereal_fertilizer_worthwhile(obs, tile):
            candidates.append(((x, y), "FERTILIZE", 80, "FERTILIZER", None))
            protected.add((x, y))
    return [
        task for task in tasks if not (task[0] in protected and task[1] == "HARVEST")
    ] + candidates


def cereal_renewal_value(obs, forecast=None, context=None):
    """Renew only when no feasible parent-preferred crop has greater value.

    The selector is extracted from the exact parent policy by the builder. Its
    finite-season scoring, production saturation and opening rules stay shared.
    An unavailable, unaffordable alternative does not prevent a funded wheat cycle.
    """
    if context is not None:
        parameters, planned, cash, seeds, selector = context
        planned = dict(planned)
        planned["WHEAT"] = max(0, planned.get("WHEAT", 0) - 1)
        preferred, scores = selector(obs, parameters, forecast, planned)
        if scores["WHEAT"] <= 0:
            return 0
        if (
            preferred != "WHEAT"
            and scores[preferred] > scores["WHEAT"]
            and (seeds.get(preferred, 0) > 0 or cash > CROPS[preferred][0] + 200)
        ):
            return 0
    remaining = min(4, 29 - obs["day"])
    units = 1 + max(0, remaining - 1)
    future_actions = max(0, remaining - 1) + 1
    return units * obs["market"]["prices"]["WHEAT"] - CROPS["WHEAT"][0] - 4 * future_actions


def cereal_route_variants(bundle, obs, forecast):
    """Optional inputs never remove a feasible watering or harvest alternative."""
    variants = [bundle]
    x, y = bundle["target"]
    tile = obs["farms"][obs["player"]]["tiles"][y][x]
    if not isinstance(tile, dict) or tile.get("crop") != "WHEAT":
        return variants
    renewal = next((i for i, (_, op, _) in enumerate(bundle["ops"]) if op == "PLANT"), None)
    if renewal is not None:
        fallback = dict(bundle)
        fallback.update(
            ops=bundle["ops"][:renewal],
            value=max(0, bundle["value"] - bundle.get("cereal_value", 0)),
            expectations={bundle["target"]: ("PLANT", "WHEAT", tile["planted_day"])},
            commissioning=False,
            cereal_unrenewed=True,
        )
        variants.append(fallback)
    if not any(op == "FERTILIZE" for _, op, _ in bundle["ops"]):
        return variants
    operations = [operation for operation in bundle["ops"] if operation[1] != "FERTILIZE"]
    # A fertilizer-enhanced HARVEST must not survive removal of its prerequisite.
    for index, (_, op, _) in enumerate(operations):
        if (
            op == "HARVEST"
            and obs["day"] - tile["planted_day"] < 4
            and obs["day"] < 29
            and tile["yield_units"] + int(not tile["watered_today"]) < 4
        ):
            operations = operations[:index]
            break
    if operations:
        fallback = dict(bundle)
        fallback.update(
            ops=operations,
            value=max(
                obs["market"]["prices"]["WHEAT"],
                tile["yield_units"] * forecast["WHEAT"] if bundle["required"] else 0,
            ),
            expectations={bundle["target"]: ("PLANT", "WHEAT", tile["planted_day"])},
            commissioning=False,
            cereal_unfertilized=True,
        )
        variants.append(fallback)
    return variants


def build(*, fertilizer=True, renewal=True, cereal_capacity=False, budget_seconds=0.065):
    """Build from the corrected fleet; ablations change only the declared service."""
    source = build_fleet()
    assert hashlib.sha256(source.encode()).hexdigest() == FLEET
    if cereal_capacity:
        source = build_fleet(cereal=True)
    if budget_seconds not in (0.065, 0.150):
        raise ValueError("Use a declared search budget")
    source = source.replace(
        "deadline = time.perf_counter() + 0.065",
        f"deadline = time.perf_counter() + {budget_seconds:.3f}",
    )
    if not fertilizer and not renewal:
        return source
    start = source.index('        use_fert = p["fertilize"] and fert_price < 70')
    end = source.index("        if values[crop] <= 0:", start)
    selector = (
        "def cereal_preferred_crop(obs, p, forecast, planned):\n"
        '    day, prices = obs["day"], obs["market"]["prices"]\n'
        '    fert_price = prices["FERTILIZER"]\n'
        '    animals = [tile for row in obs["farms"][obs["player"]]["tiles"]\n'
        '               for tile in row if isinstance(tile, dict) and "animal" in tile]\n'
        "    planned = Counter(planned)\n"
        + textwrap.indent(textwrap.dedent(source[start:end]), "    ")
        + "    return crop, values\n"
    )
    helpers = "\n\n".join(
        inspect.getsource(function)
        for function in (
            wheat_uncommitted_cash,
            cereal_fertilizer_worthwhile,
            cereal_input_orders,
            cereal_fertilizer_reserve,
            cereal_tasks,
            cereal_renewal_value,
            cereal_route_variants,
        )
    )
    source = source.replace("def agent(", selector + "\n\n" + helpers + "\n\ndef agent(", 1)
    marker = "    deadline_actions, route_claimed = daily_routes("
    assert source.count(marker) == 1
    source = source.replace(
        marker,
        "    cereal_context = (p, dict(planned), wheat_uncommitted_cash(obs, cfg, market),\n"
        "                      dict(seeds), cereal_preferred_crop)\n"
        f"    tasks = cereal_tasks(obs, tasks, plants, {fertilizer!r})\n"
        f"    market = cereal_input_orders(obs, cfg, market, {fertilizer!r},\n"
        f"                                 {renewal!r} and cereal_renewal_value(obs, forecast, cereal_context) > 0)\n"
        + marker,
    )
    marker = "    target_hands,\n):"
    assert source.count(marker) == 1
    source = source.replace(marker, "    target_hands,\n    cereal_context=None,\n):", 1)
    marker = "        target_hands,\n    )"
    assert source.count(marker) == 1
    source = source.replace(marker, "        target_hands, cereal_context,\n    )", 1)
    if fertilizer:
        old = 'if item in BASE and item != "WHEAT"'
        assert source.count(old) == 2
        source = source.replace(
            old,
            old + '\n            and not (item == "FERTILIZER" and day >= 8 and any(\n'
            '                op == "FERTILIZE" and isinstance(tile_at(target), dict)\n'
            '                and tile_at(target).get("crop") == "WHEAT"\n'
            '                for target, op, _ in plans.get(worker, {"ops": []})["ops"]))',
        )
        old = "        quantity = max(0, shed.get(item, 0) - reserve)"
        assert source.count(old) == 1
        source = source.replace(
            old,
            '        if item == "FERTILIZER":\n'
            "            reserve = max(reserve, cereal_fertilizer_reserve(obs))\n" + old,
        )
        old = '"FERTILIZE" in choices and event and forecast[crop] > prices["FERTILIZER"] + 4'
        assert source.count(old) == 1
        source = source.replace(
            old,
            '"FERTILIZE" in choices and ((event and forecast[crop] > prices["FERTILIZER"] + 4)\n'
            '                    or (day >= 8 and crop == "WHEAT" and cereal_fertilizer_worthwhile(obs, tile)))',
        )
        old = '2 if tile["fertilized_until_day"] >= day else 1\n                )\n                desired ='
        assert source.count(old) == 1
        source = source.replace(
            old,
            '2 if tile["fertilized_until_day"] >= day or fertilize else 1\n                )\n                desired =',
        )
        old = '                harvest = "HARVEST" in choices or ('
        assert source.count(old) == 1
        source = source.replace(
            old,
            '                if day >= 8 and crop == "WHEAT" and age < 4 and (fertilize or tile["fertilized_until_day"] >= day):\n'
            "                    desired = 5\n" + old,
        )
    if renewal:
        marker = "        operations, value, required, expected = [], 0.0, False, None"
        assert source.count(marker) == 1
        source = source.replace(marker, marker + "\n        cereal_value = 0.0", 1)
        marker = "                    expectations={target: expected},"
        assert source.count(marker) == 1
        source = source.replace(
            marker, marker + "\n                    cereal_value=cereal_value,", 1
        )
        old = "                    value += min(cap, units_after) * prices[crop]"
        assert source.count(old) == 1
        source = source.replace(
            old,
            old + '\n                    if crop == "WHEAT" and 8 <= day <= 26:\n'
            "                        cereal_value = cereal_renewal_value(obs, forecast, cereal_context)\n"
            "                    if cereal_value > 0:\n"
            '                        operations.extend(((target, "PLANT", "WHEAT"), (target, "WATER", None)))\n'
            '                        expected = ("CEREAL", "WHEAT", tile["planted_day"], day)\n'
            "                        value += cereal_value",
        )
        old = '        if expected and expected[0] == "PLANT":'
        assert source.count(old) == 1
        source = source.replace(
            old,
            '        if expected and expected[0] == "CEREAL":\n'
            "            if tile is None:\n"
            '                return creating and op == "WATER"\n'
            '            if kind != "PLANT" or tile.get("crop") != expected[1] or tile["planted_day"] not in expected[2:]:\n'
            "                return False\n"
            '        elif expected and expected[0] == "PLANT":',
        )
    source = source.replace(
        "        variants = [bundle]",
        "        variants = cereal_route_variants(bundle, obs, forecast)",
        1,
    )
    old = "                if best is None or rank < best[0]:"
    assert source.count(old) == 1
    source = source.replace(
        old,
        '                rank = (int(variant.get("cereal_unfertilized", False)), int(variant.get("cereal_unrenewed", False)), *rank)\n'
        + old,
    )
    compile(source, "cereal_service_candidate", "exec")
    return source
