"""Finite remaining-season crop receipts on the frozen 150 ms fleet.

The experiment changes only admissions from day 15. Current assets determine
expected market inventory; marginal cohorts then incur their own supply impact.
"""

import gzip
import hashlib
import inspect
import math
from collections import Counter
from functools import lru_cache
from pathlib import Path

from kaggriculture.agent.competitive import (
    CROPS,
    default_price_parameters,
    distance,
    inventory_quote,
)

INCUMBENT = "fca083cdb5ac82dc4ad39a4227ef60ca57c948f819b565804aa706994f8e61ba"


@lru_cache(maxsize=256)
def opportunity_schedule(crop, day, fertilize):
    """Small cohort accounting model; assumptions have official transition tests.

    Annual crops rotate after a one-day turnaround. An exhausted ongoing crop
    is followed by wheat if it can mature. Ordinary deliveries take one day;
    terminal harvests require the route controller's same-day return and sale.
    """
    sales, seeds, work, inputs = [], [], {}, []
    selected, born, fertility, last_water = crop, day, -1, day - 2
    held = 0 if CROPS[selected][3] else 1
    seed, first, last, interval, cap = CROPS[selected]
    if day + first > 29:
        return tuple(sales), tuple(seeds), tuple(work.items()), tuple(inputs)
    seeds.append((day, seed))
    work[day] = 1
    for current in range(day, 30):
        seed, first, last, interval, cap = CROPS[selected]
        age = current - born
        if age < 0:
            continue
        production_tomorrow = (
            current < 29
            and interval
            and age + 1 >= first
            and (age + 1 - first) % interval == 0
            and (age + 1 - first) // interval < cap
        )
        growth = not interval and (last + 1) // 2 <= age <= last
        water = (current < 29 or growth) and (
            age == 0 or growth or production_tomorrow or current - last_water >= 2
        )
        if production_tomorrow and fertilize and fertility < current:
            fertility = current + 2
            inputs.append(current)
            work[current] = work.get(current, 0) + 1.25
        if water:
            last_water = current
            work[current] = work.get(current, 0) + 1
            if growth:
                held = min(cap, held + 1)
        ready = age >= first and held > 0 and (interval or age >= last or current == 29)
        if ready:
            sales.append((min(29, current + 1), selected, held))
            held = 0
            work[current] = work.get(current, 0) + 1.25
            finished = not interval or age >= first + (cap - 1) * interval
            if finished:
                if interval:
                    selected, fertilize = "WHEAT", False
                    work[current] += int(current < 29)
                born = current + 1
                if born + CROPS[selected][1] > 29:
                    break
                seeds.append((born, CROPS[selected][0]))
                work[born] = work.get(born, 0) + 1
                held, fertility, last_water = 1, -1, born - 2
                continue
        if production_tomorrow:
            held = min(cap, held + (2 if water and fertility >= current else 1))
    return tuple(sales), tuple(seeds), tuple(work.items()), tuple(inputs)


def crop_opportunity_values(obs, parameters, admissions, paths, own_arrivals, target):
    """Price each additional unit against expected inventory, with no feed bonus.

    Asset supply and market feed demand are already in paths. Planned cohorts
    count only new admissions beyond publicly visible crops. The work charge is
    an economic allowance, while the unchanged controller enforces actual routes.
    """
    day = obs["day"]
    prices = obs["market"]["prices"]
    specs = obs["market"].get("params") or default_price_parameters()
    travel = min(distance(target, home) for home in ((4, 4), (5, 4), (4, 5), (5, 5))) / 2
    scores = {}
    for crop in CROPS:
        prior_cohorts = admissions[crop]
        held_seed = obs["private"]["seeds"].get(crop, 0) > prior_cohorts
        farm = obs["farms"][obs["player"]]
        approach = min(
            distance(tuple(position), target) for position in [farm["farmer"], *farm["hands"]]
        )
        clearing = int(farm["tiles"][target[1]][target[0]] is not None)
        born = day + int(obs["hour"] + approach + clearing + 2 + int(not held_seed) > 23)
        fertilize = parameters["fertilize"] and prices["FERTILIZER"] < 70 and CROPS[crop][3] > 0
        sales, seeds, work, inputs = opportunity_schedule(crop, born, fertilize)
        if not sales:
            scores[crop] = -math.inf
            continue
        value = -sum(cost for _, cost in seeds) - 4 * sum(actions + travel for _, actions in work)
        if held_seed:
            value += CROPS[crop][0]
        for future in inputs:
            index = min(len(paths["FERTILIZER"]) - 1, max(0, future - day - 1))
            value -= inventory_quote(paths["FERTILIZER"][index], specs["FERTILIZER"])
        sale_days = {}
        for future, product, units in sales:
            sale_days.setdefault(future, Counter())[product] += units
        populations = (prior_cohorts, prior_cohorts + 1)
        supplied = [Counter(), Counter()]
        for future in range(day + 1, 30):
            index = future - day - 1
            for product in sorted(set(supplied[0]) | set(supplied[1])):
                value -= own_arrivals[future][product] * (
                    inventory_quote(paths[product][index] + supplied[0][product], specs[product])
                    - inventory_quote(paths[product][index] + supplied[1][product], specs[product])
                )
            for product, units in sale_days.get(future, {}).items():
                receipts = [0, 0]
                for group, population in enumerate(populations):
                    inventory = paths[product][index] + supplied[group][product]
                    for _ in range(population * units):
                        quote = inventory_quote(inventory, specs[product])
                        receipts[group] += quote
                        # At the floor the official sale pays $1 but adds no stock.
                        if quote > 1:
                            inventory += 1
                            supplied[group][product] += 1
                value += receipts[1] - receipts[0]
        scores[crop] = value
    return scores


def build(mode="cohort", start_day=15):
    if mode not in ("incumbent", "no_multiplier", "cohort"):
        raise ValueError("Expected incumbent, no_multiplier or cohort")
    if start_day not in (3, 15):
        raise ValueError("The declared comparisons start on day 3 or day 15")
    root = Path(__file__).resolve().parents[1]
    raw = gzip.decompress((root / "reports/sources" / f"{INCUMBENT}.py.gz").read_bytes())
    assert hashlib.sha256(raw).hexdigest() == INCUMBENT
    source = raw.decode()
    if mode == "incumbent":
        return source
    marker = '        if planned["WHEAT"] < p["feed_grown"] and animals:'
    assert source.count(marker) == 1
    source = source.replace(
        marker, f'        if day < {start_day} and planned["WHEAT"] < p["feed_grown"] and animals:'
    )
    marker = "        if day < 15:"
    assert source.count(marker) == 1
    source = source.replace(marker, f"        if day < {start_day}:")
    if mode == "no_multiplier":
        return source
    marker = "    traces: dict[str, list[int]] = {item: [] for item in inventory}"
    assert source.count(marker) == 1
    source = source.replace(
        marker,
        marker
        + '\n    inventory_paths = {item: [] for item in inventory}\n    known_goods = Counter(obs["private"]["shed"])\n    for held in obs["private"]["inventories"]:\n        known_goods.update(held)',
    )
    marker = '    for farm in obs["farms"]:'
    assert source.count(marker) == 1
    source = source.replace(
        marker,
        '    for farm_index, farm in enumerate(obs["farms"]):\n        preceding_arrivals = [dict(row) for row in arrivals]',
    )
    marker = "    traces: dict[str, list[int]] = {item: [] for item in inventory}"
    source = source.replace(
        marker,
        '        if farm_index == obs["player"]:\n            own_arrivals = [{item: row[item] - preceding_arrivals[index][item] for item in inventory} for index, row in enumerate(arrivals)]\n'
        + marker,
    )
    marker = "            traces[item].append(inventory_quote(inventory[item], parameters[item]))"
    assert source.count(marker) == 1
    source = source.replace(
        marker,
        marker + "\n            inventory_paths[item].append(inventory[item] + known_goods[item])",
    )
    source = source.replace(
        "    return forecasts, traces",
        "    return forecasts, traces, inventory_paths, own_arrivals",
    )
    marker = "    forecast, _ = forecast_inventory(obs, CROPS, ANIMALS, SHOPS)"
    assert source.count(marker) == 1
    source = source.replace(
        marker,
        "    forecast, _, inventory_paths, own_arrivals = forecast_inventory(obs, CROPS, ANIMALS, SHOPS)",
    )
    marker = "        crop = max(values, key=lambda c: values[c])"
    assert source.count(marker) == 1
    source = source.replace(
        marker,
        f"        if day >= {start_day}:\n            values = crop_opportunity_values(obs, p, opportunity_admissions, inventory_paths, own_arrivals, (x, y))\n"
        + marker,
    )
    marker = "    planned = Counter(crops)"
    assert source.count(marker) == 1
    source = source.replace(marker, marker + "\n    opportunity_admissions = Counter()")
    marker = "        if seeds.get(crop, 0) > 0:"
    assert source.count(marker) == 1
    source = source.replace(marker, "        previous_seed_orders = seed_orders[crop]\n" + marker)
    marker = "        planned[crop] += 1"
    assert source.count(marker) == 1
    source = source.replace(
        marker,
        "        if seed_orders[crop] > previous_seed_orders or (hour < 23 and seeds.get(crop, 0) > opportunity_admissions[crop]):\n            opportunity_admissions[crop] += 1\n"
        + marker,
    )
    helpers = (
        "from functools import lru_cache\n\n"
        + inspect.getsource(opportunity_schedule)
        + "\n\n"
        + inspect.getsource(crop_opportunity_values)
    )
    assert source.count("def agent(") == 1
    source = source.replace("def agent(", helpers + "\n\ndef agent(")
    compile(source, "crop_opportunity_candidate", "exec")
    return source
