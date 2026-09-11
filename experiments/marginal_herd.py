"""Admission by marginal season cash, including existing-product price impact.

This is an economic screening model. Daily net trades approximate delivery and
input timing; existing crops assume feasible care, future unbought assets are
omitted, and opponent private stock is never read. It is not a replacement game
simulator or proof that the physical controller can complete every service.
"""

import gzip
import hashlib
import inspect
import math
import sys
import time
from collections import Counter
from pathlib import Path

from kaggriculture.agent.competitive import (
    ANIMALS,
    BASE,
    CROPS,
    SHOPS,
    default_price_parameters,
    inventory_quote,
)

INCUMBENT = "64fe323936dc9494add413eb956b0294658a88efe28572332c94676c68a09325"


def animal_cash_calendar(tile, day, delivery_delay=1):
    """Ideal daily service with the observed care bank and actual production order.

    Product is harvested on its production day and normally sold the next day.
    Day-29 product requires same-day harvest/delivery, a feasible but unreserved
    terminal route. No day-30 product or animal resale is credited.
    """
    _, first, interval, cap, product, _ = ANIMALS[tile["animal"]]
    placed = tile["placed_day"]
    receipts = Counter()
    held = tile["yield_units"]
    if held:
        receipts[min(29, day + delivery_delay)] += held
    pending = tile.get("pending_care_bonus", 0)
    feed_days, care_days = [], []
    production_days = [
        future
        for future in range(max(day + 1, placed + first), 30)
        if (future - placed - first) % interval == 0
    ]
    for work_day in range(max(day, placed), 29):
        if work_day != day or not tile.get("fed_today", False):
            feed_days.append(work_day)
        if work_day + 1 in production_days:
            receipts[min(29, work_day + 1 + delivery_delay)] += min(cap, 1 + pending)
            pending = 0
        # Care follows production at daily refresh, including on placement day.
        if any(event > work_day + 1 for event in production_days):
            if work_day != day or not tile.get("cared_today", False):
                care_days.append(work_day)
            pending += 1
    return {
        "product": product,
        "receipts": dict(receipts),
        "production_days": production_days,
        "feed_days": feed_days,
        "care_days": care_days,
    }


def herd_market_flow(inventory, spec, own, rival, quote, deadline=None):
    """Single-commodity paired orders; positive quantity sells, negative buys.

    Integer flows reproduce official simultaneous quotes and the sale-price-one
    supply exception. Fractional units represent expected scenario flows only.
    """
    remaining = [abs(own), abs(rival)]
    directions = [1 if own >= 0 else -1, 1 if rival >= 0 else -1]
    own_cash = 0.0
    iteration = 0
    while max(remaining) > 1e-9:
        if iteration % 16 == 0 and deadline is not None and time.perf_counter() >= deadline:
            raise TimeoutError("marginal_herd_budget")
        quantities = [min(1.0, value) for value in remaining]
        prices = [
            quote(inventory - (1 if direction < 0 else 0), spec) if quantity else 0
            for quantity, direction in zip(quantities, directions, strict=True)
        ]
        for player, (quantity, direction, price) in enumerate(
            zip(quantities, directions, prices, strict=True)
        ):
            if not quantity:
                continue
            if player == 0:
                own_cash += direction * quantity * price
            if direction < 0 or price > 1:
                inventory += direction * quantity
            remaining[player] -= quantity
        iteration += 1
    return inventory, own_cash


def herd_projection_inputs(obs, proposal=None):
    """Build current-asset receipts and input obligations without hidden stock."""
    day = obs["day"]
    prices = obs["market"]["prices"]
    own = obs["player"]
    flows = [[Counter() for _ in range(30)] for _ in range(2)]
    live = [[0 for _ in range(30)] for _ in range(2)]
    proposed_calendar = None
    for item in BASE:
        flows[0][day][item] += obs["private"]["shed"].get(item, 0)
        flows[0][day][item] += sum(i.get(item, 0) for i in obs["private"]["inventories"])
    for role, farm in enumerate((obs["farms"][own], obs["farms"][1 - own])):
        animals = [
            dict(tile)
            for row in farm["tiles"]
            for tile in row
            if isinstance(tile, dict) and "animal" in tile
        ]
        if role == 0:
            held = Counter(obs["private"]["shed"])
            for inventory in obs["private"]["inventories"]:
                held.update(inventory)
            queue = [name for name in ANIMALS for _ in range(held[name])]
            if proposal:
                queue.append(proposal)
            for index, name in enumerate(queue):
                tile = {
                    "animal": name,
                    "placed_day": day + 1 + index // 2,
                    "yield_units": 0,
                    "pending_care_bonus": 0,
                    "fed_today": False,
                    "cared_today": False,
                    "fertilizer_available": False,
                }
                animals.append(tile)
                if proposal and index == len(queue) - 1:
                    proposed_calendar = animal_cash_calendar(tile, day)
        for tile in animals:
            calendar = animal_cash_calendar(tile, day)
            for date, amount in calendar["receipts"].items():
                flows[role][date][calendar["product"]] += amount
            for date in calendar["feed_days"]:
                flows[role][date]["WHEAT"] -= 1
            for date in range(max(day, tile["placed_day"]), 29):
                live[role][date] += 1
            # Collection is imperfect under the unchanged controller. The same
            # 75% assumption applies to baseline and proposed manure receipts.
            if tile.get("fertilizer_available"):
                flows[role][min(29, day + 1)]["FERTILIZER"] += 0.75
            for date in range(max(day + 1, tile["placed_day"] + 1), 29):
                flows[role][date + 1]["FERTILIZER"] += 0.75
        for row in farm["tiles"]:
            for tile in row:
                if not isinstance(tile, dict) or tile.get("kind") != "PLANT":
                    continue
                crop = tile["crop"]
                _, first, last, interval, cap = CROPS[crop]
                planted = tile["planted_day"]
                if interval:
                    flows[role][min(29, day + 1)][crop] += tile["yield_units"]
                    until = tile["fertilized_until_day"]
                    fertilize = prices[crop] > prices["FERTILIZER"] * 0.7 + 10
                    for event in range(planted + first, planted + first + cap * interval, interval):
                        if not day < event <= 29:
                            continue
                        if fertilize and until < event - 1:
                            flows[role][event - 1]["FERTILIZER"] -= 1
                            until = event + 1
                        flows[role][min(29, event + 1)][crop] += 2 if until >= event - 1 else 1
                else:
                    harvest = max(day, planted + (first if crop == "MELON" else last))
                    if harvest > 29:
                        continue
                    units = tile["yield_units"]
                    for work_day in range(day, harvest + 1):
                        age = work_day - planted
                        if (last + 1) // 2 <= age <= last and not (
                            work_day == day and tile["watered_today"]
                        ):
                            units += 2 if tile["fertilized_until_day"] >= work_day else 1
                    flows[role][min(29, harvest + 1)][crop] += min(cap, units)
    return flows, live, proposed_calendar


def project_herd_cash(obs, inputs, future_shop_scale, quote, deadline=None, items=None):
    """Daily net trade scenario with public shops and both farms' current cohorts."""
    flows, _, _ = inputs
    day, hour = obs["day"], obs["hour"]
    inventory = dict(obs["market"]["inventory"])
    params = obs["market"].get("params") or default_price_parameters()
    shops = obs["town"]["unlocked_shops"]
    selected = tuple(BASE) if items is None else tuple(items)
    cash_by_day, product_cash = [], Counter()
    product_cash_by_day = {item: [] for item in selected}
    cash = 0.0
    for date in range(day, 30):
        if deadline is not None and time.perf_counter() >= deadline:
            raise TimeoutError("marginal_herd_budget")
        demand = Counter({item: 0 if item == "FERTILIZER" else 1 for item in BASE})
        for shop in shops:
            products = SHOPS[shop]
            for item in products:
                demand[item] += 12 if len(products) == 1 else 6
        extra = min(8 - len(shops), max(0, date // 3 - day // 3)) * future_shop_scale
        for products in SHOPS.values():
            for item in products:
                demand[item] += extra * (12 if len(products) == 1 else 6) / len(SHOPS)
        for item in selected:
            # Spread remaining public demand around today's aggregate trades.
            # This is not a prediction of the opponent's intraday sell sequence.
            quantity = demand[item] * ((24 - hour) / 24 if date == day else 1)
            inventory[item] -= quantity * 0.5
            inventory[item], earned = herd_market_flow(
                inventory[item],
                params[item],
                flows[0][date][item],
                flows[1][date][item],
                quote,
                deadline,
            )
            inventory[item] -= quantity * 0.5
            product_cash[item] += earned
            product_cash_by_day[item].append(product_cash[item])
            cash += earned
        cash_by_day.append(cash)
    return {
        "cash": cash,
        "cash_by_day": cash_by_day,
        "product_cash": dict(product_cash),
        "product_cash_by_day": product_cash_by_day,
    }


def marginal_herd_values(obs, configuration=None, deadline=None):
    """Value additions after their effect on all existing own sales and inputs."""
    cfg = configuration or {}
    # The local cache keys parameter identity; keep every parameter mapping alive
    # and shared across all scenarios, including when defaults were required.
    params = obs["market"].get("params") or default_price_parameters()
    obs = {**obs, "market": {**obs["market"], "params": params}}
    farm = obs["farms"][obs["player"]]
    prices = obs["market"]["prices"]
    day = obs["day"]
    baseline = herd_projection_inputs(obs)
    quote_cache = {}

    def quote(inventory, spec):
        key = id(spec), inventory
        if key not in quote_cache:
            quote_cache[key] = inventory_quote(inventory, spec)
        return quote_cache[key]

    scenarios = ((1.0, 0.75), (0.0, 0.25))
    base_values = [
        project_herd_cash(obs, baseline, scale, quote, deadline) for scale, _ in scenarios
    ]
    half = len(farm["tiles"]) // 2
    depots = [(half - 1, half - 1), (half, half - 1), (half - 1, half), (half, half)]
    free = [
        (x, y)
        for y, row in enumerate(farm["tiles"])
        for x, tile in enumerate(row)
        if tile is None
        or (
            isinstance(tile, dict)
            and tile.get("kind") in ("WEED", "COOP", "PASTURE")
            and "animal" not in tile
        )
    ]
    if not free:
        return {}
    distance = min(abs(x - dx) + abs(y - dy) for x, y in free for dx, dy in depots)
    plants = sum(
        isinstance(t, dict) and t.get("kind") == "PLANT" for row in farm["tiles"] for t in row
    )
    animals = sum(isinstance(t, dict) and "animal" in t for row in farm["tiles"] for t in row)
    hands = min(12, max(4, math.ceil((plants * 1.4 + animals * 4.5) / 8)))
    a, b, daily_wages = 1, 1, 0
    for _ in range(hands):
        daily_wages += a * int(cfg.get("farmHandCostMult", 1))
        a, b = b, a + b
    values = {}
    for animal, spec in ANIMALS.items():
        if farm["money"] <= spec[0] + max(150, (animals + 1) * prices["WHEAT"]):
            continue
        proposed = herd_projection_inputs(obs, animal)
        calendar = proposed[2]
        if not calendar["production_days"]:
            continue
        days = len(calendar["feed_days"])
        manure = max(0, days - 1) * 0.75
        units = sum(calendar["receipts"].values())
        actions = (
            3
            + 2 * distance
            + days
            + len(calendar["care_days"])
            + manure
            + math.ceil(days / 3)
            + len(calendar["receipts"])
            + (units + manure) / 5
            + days * (0.5 + distance / 4)
        )
        service_cost = actions * 4
        results, net = [], 0.0
        solvent = True
        affected = (calendar["product"], "WHEAT", "FERTILIZER")
        for (scale, weight), base in zip(scenarios, base_values, strict=True):
            after = project_herd_cash(obs, proposed, scale, quote, deadline, affected)
            base_affected = sum(base["product_cash"].get(item, 0) for item in affected)
            marginal = after["cash"] - base_affected - spec[0] - service_cost
            net += weight * marginal
            # Existing assets are sunk; prospective animal cost is charged once.
            # The cash check excludes later unbought investment and is a runway
            # screen, not an execution-level guarantee of every future purchase.
            minimum_cash = min(
                farm["money"]
                - spec[0]
                + base["cash_by_day"][index]
                + value
                - sum(base["product_cash_by_day"][item][index] for item in affected)
                - (index + 1) * daily_wages
                for index, value in enumerate(after["cash_by_day"])
            )
            solvent &= minimum_cash >= 120
            results.append(
                {
                    "future_shop_scale": scale,
                    "weight": weight,
                    "net": marginal,
                    "minimum_projected_cash": minimum_cash,
                    "product_cash_change": {
                        item: after["product_cash"].get(item, 0) - base["product_cash"].get(item, 0)
                        for item in affected
                    },
                }
            )
        values[animal] = {
            "net": net,
            "solvent": solvent,
            "purchase_cost": spec[0],
            "service_cost": service_cost,
            "service_actions": actions,
            "placement_day": day + 1,
            "scenarios": results,
        }
    return values


def marginal_herd_purchase(obs, configuration=None, fallback=None, budget_seconds=0.05):
    """Prepared incumbent purchase is the only budget fallback; diagnostics persist."""
    try:
        values = marginal_herd_values(obs, configuration, time.perf_counter() + budget_seconds)
    except TimeoutError:
        print("marginal_herd_budget_fallback", file=sys.stderr)
        return fallback
    accepted = [(v["net"], animal) for animal, v in values.items() if v["solvent"] and v["net"] > 0]
    return max(accepted)[1] if accepted else None


def build(*, base=INCUMBENT):
    content = gzip.decompress((Path("reports/sources") / f"{base}.py.gz").read_bytes())
    assert hashlib.sha256(content).hexdigest() == base
    source = content.decode()
    helpers = "\n\n".join(
        inspect.getsource(function)
        for function in (
            animal_cash_calendar,
            herd_market_flow,
            herd_projection_inputs,
            project_herd_cash,
            marginal_herd_values,
            marginal_herd_purchase,
        )
    )
    source = source.replace("def agent(obs:", helpers + "\n\ndef agent(obs:", 1)
    marker = "    # Labour has Fibonacci marginal costs."
    assert source.count(marker) == 1
    source = source.replace(
        marker,
        '    if (8 <= day <= p["animal_stop"] and sum(stock[a] for a in ANIMALS) < 2\n'
        "            and len(animals) + sum(stock[a] for a in ANIMALS) < 18\n"
        "            and len(animals) < len(cells) - 2):\n"
        "        purchase = marginal_herd_purchase(obs, cfg, purchase)\n\n" + marker,
        1,
    )
    compile(source, "marginal_herd", "exec")
    return source
