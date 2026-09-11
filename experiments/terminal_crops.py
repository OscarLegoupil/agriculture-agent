"""Finite terminal crop rotations with observable demand and replacement costs."""

from __future__ import annotations

import gzip
import hashlib
import inspect
import json
from functools import cache, lru_cache
from pathlib import Path

from kaggriculture.agent.competitive import CROPS, distance

INCUMBENT = "64fe323936dc9494add413eb956b0294658a88efe28572332c94676c68a09325"


@lru_cache(maxsize=2048)
def annual_contracts(crop, planted_day, hour, approach, home_distance, fertilize=False):
    """Enumerate surviving annual watering calendars through actual sale delivery.

    The interpreter starts a planted tile with one consecutive unwatered day.
    Consequently planting-day WATER is mandatory. Annual WATER creates units
    immediately; maturity gates HARVEST, and expiry starts only afterward.
    Each day's service trip is charged from the nightly worker reset at the shed.
    """
    seed, first, last, interval, cap = CROPS[crop]
    if interval or crop not in ("WHEAT", "CARROT"):
        return []
    growth_start = (last + 1) // 2
    result = []
    latest_age = min(last, 29 - planted_day)
    if latest_age < first:
        return []
    # The controller harvests at the last growth opportunity. Earlier harvests
    # would require a separate execution commitment and are not credited here.
    for age in (latest_age,):
        harvest_day = planted_day + age
        for mask in range(1 << (age + 1)):
            units, dry = 1, 1
            calendar, actions, travel = [], 0, 0
            valid = True
            for offset in range(age + 1):
                watered = bool(mask & (1 << offset))
                operations = ["PLANT"] if offset == 0 else []
                if fertilize and offset == growth_start:
                    operations.extend(("PICKUP_FERTILIZER", "FERTILIZE"))
                if watered:
                    operations.append("WATER")
                    if growth_start <= offset <= last:
                        units = min(cap, units + (2 if fertilize else 1))
                if offset == age:
                    operations.append("HARVEST")
                    if harvest_day == 29:
                        operations.append("DROP")
                else:
                    dry = 0 if watered else dry + 1
                    if dry >= 2:
                        valid = False
                        break
                if operations:
                    trip = approach if offset == 0 else home_distance
                    # Pickup occurs before departing the shed on its service day.
                    occupied = trip + len(operations)
                    if harvest_day == 29 and offset == age:
                        occupied += home_distance
                    available = (
                        24 - hour if offset == 0 else 23 if planted_day + offset == 29 else 24
                    )
                    if occupied > available:
                        valid = False
                        break
                    travel += trip + (home_distance if harvest_day == 29 and offset == age else 0)
                    actions += len(operations)
                    calendar.append((planted_day + offset, tuple(operations)))
            if not valid:
                continue
            result.append(
                dict(
                    crop=crop,
                    seed=seed,
                    planted_day=planted_day,
                    harvest_day=harvest_day,
                    sale_day=min(29, harvest_day + 1),
                    units=units,
                    fertilize=fertilize,
                    calendar=calendar,
                    actions=actions,
                    travel=travel,
                )
            )
    # Retain Pareto-efficient calendars for a given harvest date and yield.
    best = {}
    for contract in result:
        key = contract["harvest_day"], contract["units"]
        cost = contract["actions"] + contract["travel"]
        if key not in best or cost < best[key]["actions"] + best[key]["travel"]:
            best[key] = contract
    return list(best.values())


def terminal_rotation(day, hour, approach, home_distance, quote_by_day, seed_costs=None):
    """Choose a short sequence of unfertilized crops by total remaining receipts.

    This is a feasible single-plot calendar, not a whole-farm simulator. The
    scheduler has not established reliable future fertilizer prerequisites, so
    deployed valuations use the verified unfertilized contracts only.
    """
    seed_costs = seed_costs or {crop: CROPS[crop][0] for crop in ("WHEAT", "CARROT")}

    @cache
    def solve(start, start_hour, first_approach, opening):
        best = (0.0, ())
        for crop in ("WHEAT", "CARROT"):
            for contract in annual_contracts(
                crop, start, start_hour, first_approach, home_distance
            ):
                sale = contract["sale_day"]
                # Four cash per action is an explicit labor opportunity charge;
                # measured travel is charged equally, not an eight-tiles proxy.
                cost = seed_costs[crop] if opening else CROPS[crop][0]
                net = contract["units"] * quote_by_day[crop][sale] - cost
                net -= 4 * (contract["actions"] + contract["travel"])
                following = (0.0, ())
                if contract["harvest_day"] < 27:
                    following = solve(contract["harvest_day"] + 1, 0, home_distance, False)
                value = net + following[0]
                if value > best[0]:
                    best = value, (contract, *following[1])
        return best

    value, sequence = solve(day, hour, approach, True)
    return {"value": value, "sequence": sequence, "crop": sequence[0]["crop"] if sequence else None}


def terminal_choices(obs, positions, access, traces):
    """Price late rotations and compare against an optimistic keep-crop bound."""
    day, hour = obs["day"], obs["hour"]
    if day < 18 or day >= 28:
        return {}
    farm, private = obs["farms"][obs["player"]], obs["private"]
    quotes = {}
    for crop in CROPS:
        current = obs["market"]["prices"][crop]
        quotes[crop] = {
            future: current
            if future == day
            else 0.5 * current + 0.5 * traces[crop][future - day - 1]
            for future in range(day, 30)
        }
    proposed = {}
    reserved_units = {crop: 0 for crop in CROPS}
    remaining_seeds = dict(private["seeds"])
    sites = []
    for y, row in enumerate(farm["tiles"]):
        for x, tile in enumerate(row):
            if tile == "LOCKED" or (isinstance(tile, dict) and "animal" in tile):
                continue
            if (
                isinstance(tile, dict)
                and tile.get("kind") == "PLANT"
                and (not CROPS[tile["crop"]][3] or tile["yield_units"])
            ):
                continue
            sites.append(((x, y), tile))
    sites.sort(key=lambda item: (min(distance(item[0], home) for home in access), item[0]))
    for target, tile in sites:
        clearing = tile is not None
        approach = min(distance(pos, target) for pos in positions) + int(clearing)
        home_distance = min(distance(target, home) for home in access)
        # Seeds purchased this turn become usable only on the following action.
        missing_seed = any(remaining_seeds.get(crop, 0) <= 0 for crop in ("WHEAT", "CARROT"))
        plant_hour = hour + int(missing_seed)
        if plant_hour + approach + 2 > 24:
            continue
        local_quotes = {
            crop: {
                future: price / (1 + reserved_units[crop] / 150) for future, price in values.items()
            }
            for crop, values in quotes.items()
        }
        costs = {
            crop: 0 if remaining_seeds.get(crop, 0) > 0 else CROPS[crop][0]
            for crop in ("WHEAT", "CARROT")
        }
        choice = terminal_rotation(day, plant_hour, approach, home_distance, local_quotes, costs)
        if not choice["sequence"]:
            continue
        keep = 0
        if isinstance(tile, dict) and tile.get("kind") == "PLANT":
            crop = tile["crop"]
            _, first, _, interval, cap = CROPS[crop]
            for index in range(cap):
                production = tile["planted_day"] + first + index * interval
                if day < production <= 29:
                    # Optimistic retention bound: two units/event, free future
                    # feedstock and service, no holding loss. Replacing it must
                    # pay its complete new seed and service bill plus a margin.
                    keep += 2 * quotes[crop][production]
        if choice["value"] <= keep + (20 if clearing else 0):
            continue
        choice["gain"] = choice["value"] - keep
        choice["priority"] = min(80, max(42, 30 + choice["gain"] / 12))
        proposed[target] = choice
        remaining_seeds[choice["crop"]] = max(0, remaining_seeds.get(choice["crop"], 0) - 1)
        for contract in choice["sequence"]:
            reserved_units[contract["crop"]] += contract["units"]
    return proposed


def build():
    root = Path(__file__).resolve().parents[1]
    raw = gzip.decompress((root / "reports/sources" / f"{INCUMBENT}.py.gz").read_bytes())
    assert hashlib.sha256(raw).hexdigest() == INCUMBENT
    source = raw.decode()
    source = source.replace(
        "import math\n", "import math\nfrom functools import cache, lru_cache\n"
    )
    source = source.replace(
        "    forecast, _ = forecast_inventory(obs, CROPS, ANIMALS, SHOPS)",
        "    forecast, terminal_traces = forecast_inventory(obs, CROPS, ANIMALS, SHOPS)\n"
        "    rotations = terminal_choices(obs, positions, shed_tiles, terminal_traces)",
    )
    marker = '    for x, y, tile in plants:\n        crop = tile["crop"]'
    replacement = """    for x, y, tile in plants:
        rotation = rotations.get((x, y))
        if rotation and seeds.get(rotation["crop"], 0) > 0:
            task(x, y, "DIG", rotation["priority"])
            continue
        crop = tile["crop"]"""
    assert source.count(marker) == 1
    source = source.replace(marker, replacement)
    source = source.replace(
        "        if ripe and not water_before_harvest:",
        '        terminal_wait = day >= 18 and crop in ("WHEAT", "CARROT") and age < min(last, 29 - tile["planted_day"])\n'
        "        if ripe and not water_before_harvest and not terminal_wait:",
    )
    marker = "    seed_orders: Counter[str] = Counter()"
    replacement = """    seed_orders: Counter[str] = Counter()
    for target, rotation in rotations.items():
        tile = board[target[1]][target[0]]
        crop = rotation["crop"]
        if isinstance(tile, dict) and tile.get("kind") == "PLANT":
            if not seeds.get(crop, 0) and seed_orders[crop] < 4 and cash > CROPS[crop][0] + 200:
                seed_orders[crop] += 1
                cash -= CROPS[crop][0]"""
    assert source.count(marker) == 1
    source = source.replace(marker, replacement)
    marker = "        crop = max(values, key=lambda c: values[c])"
    replacement = """        if day >= 18:
            rotation = rotations.get((x, y))
            if not rotation:
                continue
            values = {rotation["crop"]: rotation["value"]}
        crop = max(values, key=lambda c: values[c])"""
    assert source.count(marker) == 1
    source = source.replace(marker, replacement)
    source = source.replace(
        'task(x, y, "PLANT", 42, arg=crop)',
        'task(x, y, "PLANT", rotations.get((x, y), {}).get("priority", 42), arg=crop)',
    )
    source = source.replace(
        'task(x, y, "DIG", 35)',
        'task(x, y, "DIG", rotations.get((x, y), {}).get("priority", 35))',
    )
    helpers = "\n\n".join(
        inspect.getsource(fn) for fn in (annual_contracts, terminal_rotation, terminal_choices)
    )
    source = source.replace("def agent(", helpers + "\n\ndef agent(")
    compile(source, "terminal_crops_candidate", "exec")
    return source


def official_probe():
    """Run four single-cohort cash-flow witnesses through the full interpreter.

    The opponent passes and town demand evolves normally. This measures model
    contracts, not competitive strength or achievable multi-plot throughput.
    """
    from kaggle_environments import make

    rows = []
    for crop in ("WHEAT", "CARROT"):
        for fertilize in (False, True):
            contract = max(
                annual_contracts(crop, 0, 1, 0, 0, fertilize),
                key=lambda value: (value["units"], -value["actions"]),
            )
            env = make("kaggriculture", configuration={"seed": 0})
            env.reset()
            initial_cash = env.state[0].observation.farms[0]["money"]
            calendar = dict(contract["calendar"])
            operations = {}
            for day, actions in calendar.items():
                for index, op in enumerate(actions):
                    hour = index + int(day == 0)
                    operations[day * 24 + hour] = (
                        ["PLANT", crop]
                        if op == "PLANT"
                        else ["PICKUP", "FERTILIZER", 1]
                        if op == "PICKUP_FERTILIZER"
                        else [op]
                    )
            delivered = None
            for step in range(contract["sale_day"] * 24 + 1):
                market = []
                if step == 0:
                    market.append(["BUY_SEED", crop, 1])
                    if fertilize:
                        market.append(["BUY_PRODUCT", "FERTILIZER", 1])
                if step == contract["sale_day"] * 24:
                    delivered = env.state[0].observation.private["shed"].get(crop, 0)
                    market.append(["SELL", crop, delivered])
                env.step([{"farmer": operations.get(step, ["PASS"]), "market": market}, {}])
            final_cash = env.state[0].observation.farms[0]["money"]
            rows.append(
                {
                    "crop": crop,
                    "fertilize": fertilize,
                    "units_expected": contract["units"],
                    "units_delivered": delivered,
                    "seed_cost": CROPS[crop][0],
                    "fertilizer_cost": 100 if fertilize else 0,
                    "sale_day": contract["sale_day"],
                    "worker_actions": contract["actions"],
                    "net_cash": final_cash - initial_cash,
                    "net_after_action_charge": final_cash - initial_cash - 4 * contract["actions"],
                }
            )
    return rows


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--probe", action="store_true")
    args = parser.parse_args()
    print(
        json.dumps(official_probe(), indent=2)
        if args.probe
        else hashlib.sha256(build().encode()).hexdigest()
    )
