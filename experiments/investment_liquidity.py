"""Collect existing saleable stock to unblock a specific early investment.

The existing land, crop, animal and labor purchase gates remain unchanged.
Current quotes only decide whether to dispatch real collection/delivery work;
unexecuted revenue is never credited to the policy's spendable cash.
"""

import inspect

from experiments.daily_routes import build as fleet_build

from kaggriculture.agent.competitive import (
    ANIMALS,
    BASE,
    CROPS,
    default_price_parameters,
    distance,
    inventory_quote,
)


def investment_liquidity_possible(obs, cfg, positions, inventories, tasks, access, cash_needed):
    """Conservative feasibility screen for simultaneous, disjoint short deliveries.

    Each quoted lot has its own worker, observed source and actual round-trip
    cost, including collection and DROP. Reserve current shed capacity for all
    accepted lots. Prices may change before delivery; the normal purchase gate
    will still require actual money in a later observation.
    """
    if not 4 <= obs["day"] < 15 or cash_needed <= 0 or obs["hour"] >= 12:
        return False
    board = obs["farms"][obs["player"]]["tiles"]
    capacity = cfg.get("shedCapacity", 100) - sum(obs["private"]["shed"].values())
    if capacity <= 0 or not positions:
        return False
    required_fertilizer = any(required == "FERTILIZER" for _, _, _, required, _ in tasks)

    def saleable(item):
        return (
            item in BASE and item != "WHEAT" and not (item == "FERTILIZER" and required_fertilizer)
        )

    choices = {}
    for target, op, _, _, _ in tasks:
        if op in ("HARVEST", "COLLECT_FERTILIZER"):
            choices.setdefault(target, set()).add(op)
    lots = []
    for worker, pos in enumerate(positions):
        home_distance = min(distance(pos, depot) for depot in access)
        cargo = {item: n for item, n in inventories[worker].items() if n > 0 and saleable(item)}
        if cargo:
            lots.append((worker, None, home_distance + 1, cargo, sum(inventories[worker].values())))
        for target, operations in choices.items():
            tile = board[target[1]][target[0]]
            if not isinstance(tile, dict):
                continue
            goods, count = dict(cargo), 0
            if "HARVEST" in operations and tile.get("yield_units", 0) > 0:
                product = ANIMALS[tile["animal"]][4] if "animal" in tile else tile.get("crop")
                mature = "animal" in tile or (
                    product in CROPS and obs["day"] >= tile["planted_day"] + CROPS[product][1]
                )
                if mature and saleable(product):
                    goods[product] = goods.get(product, 0) + tile["yield_units"]
                    count += 1
            if (
                "COLLECT_FERTILIZER" in operations
                and tile.get("fertilizer_available")
                and saleable("FERTILIZER")
            ):
                goods["FERTILIZER"] = goods.get("FERTILIZER", 0) + 1
                count += 1
            if not count:
                continue
            cost = (
                distance(pos, target) + count + min(distance(target, depot) for depot in access) + 1
            )
            units = sum(inventories[worker].values()) + sum(goods.values()) - sum(cargo.values())
            lots.append((worker, target, cost, goods, units))
    market = obs["market"]
    params = market.get("params") or default_price_parameters()
    sold, used_workers, used_sources = {}, set(), set()
    receipts = 0
    lots.sort(
        key=lambda lot: (
            -sum(n * market["prices"][item] for item, n in lot[3].items()) / lot[2],
            lot[2],
            lot[0],
            lot[1] or (-1, -1),
        )
    )
    for worker, target, cost, goods, units in lots:
        if worker in used_workers or (target is not None and target in used_sources):
            continue
        # Leave at least eight same-day actions after the latest accepted drop.
        # The fleet will replan feeding/watering from observed acknowledgments.
        if obs["hour"] + cost > 16 or units > capacity:
            continue
        used_workers.add(worker)
        if target is not None:
            used_sources.add(target)
        capacity -= units
        for item, amount in goods.items():
            already = sold.get(item, 0)
            receipts += sum(
                inventory_quote(market["inventory"][item] + already + offset, params[item])
                for offset in range(amount)
            )
            sold[item] = already + amount
        if receipts >= cash_needed:
            return True
    return False


def build(*, seed_capital=True):
    """Build from the frozen 150 ms cereal fleet, with observed-capital routing."""
    source = fleet_build(cereal=True, budget_seconds=0.150)
    marker = '    feed_need = sum(not t["fed_today"] for _, _, t in animals) if day < 29 else 0'
    assert source.count(marker) == 1
    source = source.replace(marker, "    investment_cash_need = 0\n" + marker)
    original = """            market.append(["BUY_LAND"])
            cash -= cost"""
    assert source.count(original) == 1
    source = source.replace(
        original,
        original
        + '\n        else:\n            investment_cash_need = cost + max(300, feed_need * prices["WHEAT"] + 150) + 1 - cash',
    )
    if seed_capital:
        original = """            seed_orders[crop] += 1
            cash -= CROPS[crop][0]"""
        assert source.count(original) == 1
        source = source.replace(
            original,
            original
            + """
        elif cash <= CROPS[crop][0] + (30 if day < 2 else 200) and seed_orders[crop] < 4:
            missing = CROPS[crop][0] + (30 if day < 2 else 200) + 1 - cash
            investment_cash_need = min(investment_cash_need or missing, missing)""",
        )
    original = "    target_hands,\n):"
    assert source.count(original) == 1
    source = source.replace(original, "    target_hands,\n    investment_cash_need,\n):")
    original = "        target_hands,\n    )"
    assert source.count(original) == 1
    source = source.replace(original, "        target_hands,\n        investment_cash_need,\n    )")
    original = """    liquidity_needed = (
        len(farm["hands"]) < target_hands and farm["money"] < hire_runway and hour < 8
    )"""
    assert source.count(original) == 1
    source = source.replace(
        original,
        original
        + """ or investment_liquidity_possible(
        obs, cfg, positions, inventories, tasks, access, investment_cash_need
    )""",
    )
    original = 'or (collecting and (day == 29 or farm["money"] < 500))'
    assert source.count(original) == 1
    source = source.replace(
        original, 'or (collecting and (liquidity_needed or day == 29 or farm["money"] < 500))'
    )
    source = source.replace(
        "def daily_routes(",
        inspect.getsource(investment_liquidity_possible) + "\n\ndef daily_routes(",
        1,
    )
    compile(source, "investment_liquidity", "exec")
    return source
