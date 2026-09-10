"""Bounded shop-scenario marginal herd valuation; isolated development candidate."""

import argparse
import hashlib
import inspect
import json
import random
import sys
import time
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

from benchmark import episode, provenance, snapshot
from phase2_logistics import replace
from phase3_interactions import build as interaction

BASE_SHA256 = "521467d45a0e2739d634ec628009753fe8e3844633bdc6e6f733f45521489a59"


def animal_calendar(tile, day, specs):
    """Ideal daily care, capped first harvest, next-day sale, no terminal assets.

    Quantities are units, indexed by sale day. A prospective tile is placed one
    day after admission. Existing ages and accumulated care remain intact.
    """
    _, first, interval, cap, product, _ = specs[tile["animal"]]
    placed = tile["placed_day"]
    sales = {product: [0.0] * 30, "FERTILIZER": [0.0] * 30, "WHEAT": [0.0] * 30}
    pending = tile.get("pending_care_bonus", 0)
    if placed <= day and day < 29:
        sales[product][day + 1] += tile.get("yield_units", 0)
        sales["FERTILIZER"][day + 1] += int(tile.get("fertilizer_available", False))
    for worked_day in range(max(day, placed), 28):
        if worked_day > day or placed > day:
            sales["WHEAT"][worked_day] -= 1
        next_day = worked_day + 1
        age = next_day - placed
        if age >= first and (age - first) % interval == 0:
            sales[product][next_day + 1] += min(cap, 1 + pending)
            pending = 0
        pending += 1
        sales["FERTILIZER"][next_day + 1] += 1
    return sales


def scenario_animal_values(obs, specs, crops, shops, quote, parameters, budget=0.12):
    """Eight stratified future-shop paths; marginal cash of one executable cohort.

    The pseudo-random generator is local and constant, unrelated to game seeds.
    Each future unlock has an independent permutation of the shop catalog; each
    path can repeat shops, matching with-replacement unlocks. Current shops are
    known. Future realized state and opponent private inventory are never read.
    """
    deadline = time.perf_counter() + budget
    day = obs["day"]
    items = ("MILK", "WOOL", "EGG", "FERTILIZER", "WHEAT")
    all_supply = {item: [0.0] * 30 for item in items}
    own_supply = {item: [0.0] * 30 for item in items}
    for seat, farm in enumerate(obs["farms"]):
        tiles = [tile for row in farm["tiles"] for tile in row if isinstance(tile, dict)]
        if seat == obs["player"]:
            for inv in [obs["private"]["shed"], *obs["private"]["inventories"]]:
                for animal in specs:
                    tiles.extend(
                        dict(animal=animal, placed_day=day + 1) for _ in range(inv.get(animal, 0))
                    )
        for tile in tiles:
            if "animal" in tile:
                projected = animal_calendar(tile, day, specs)
            elif tile.get("crop") == "WHEAT":
                target = max(day + 1, tile["planted_day"] + crops["WHEAT"][2] - 1)
                projected = {"WHEAT": [0.0] * 30}
                if target < 29:
                    projected["WHEAT"][target + 1] = min(
                        crops["WHEAT"][4], tile["yield_units"] + target - day
                    )
            else:
                continue
            for item, series in projected.items():
                for future in range(day + 1, 30):
                    all_supply[item][future] += series[future]
                    if seat == obs["player"]:
                        own_supply[item][future] += series[future]

    catalog = list(shops)
    rng = random.Random(61423)
    columns = []
    for _ in range(8 - len(obs["town"]["unlocked_shops"])):
        permutation = catalog.copy()
        rng.shuffle(permutation)
        columns.append(permutation)
    schedules = []
    for scenario in range(len(catalog)):
        active = list(obs["town"]["unlocked_shops"])
        daily = []
        for future in range(day + 1, 30):
            added = min(len(columns), max(0, future // 3 - day // 3))
            active = [*obs["town"]["unlocked_shops"], *(columns[i][scenario] for i in range(added))]
            demand = {item: float(item != "FERTILIZER") for item in items}
            for shop in active:
                for item in shops[shop]:
                    if item in demand:
                        demand[item] += 12 if len(shops[shop]) == 1 else 6
            daily.append(demand)
        schedules.append(daily)

    values = {}
    for animal, (cost, _, _, _, product, _) in specs.items():
        marginal = animal_calendar(dict(animal=animal, placed_day=day + 1), day, specs)
        samples = []
        for demands in schedules:
            if time.perf_counter() >= deadline:
                print("scenario_investment_budget_fallback", file=sys.stderr)
                return {}
            inventories = {
                item: [obs["market"]["inventory"][item]] * 2
                for item in (product, "FERTILIZER", "WHEAT")
            }
            value = 0.0
            for offset, future in enumerate(range(day + 1, 30)):
                for item, pair in inventories.items():
                    old = all_supply[item][future]
                    delta = marginal[item][future]
                    demand = demands[offset][item]
                    prices = []
                    for index, supply in enumerate((old, old + delta)):
                        # Simpson average approximates intraday price impact. It is
                        # exact for the unclipped linear/square branches, not a
                        # claim of exact market execution or future delivery.
                        start = pair[index] - demand * 0.5
                        prices.append(
                            (
                                quote(start, parameters[item])
                                + 4 * quote(start + supply * 0.5, parameters[item])
                                + quote(start + supply, parameters[item])
                            )
                            / 6
                        )
                        pair[index] += supply - demand
                    own = own_supply[item][future]
                    value += (own + delta) * prices[1] - own * prices[0]
            samples.append(value)
        # 4 cash/action: feed, care, manure, fractional pickup/transport, and
        # periodic harvest, plus placement/build. Cash costs use sale calendars.
        days = max(0, 28 - (day + 1))
        actions = days * (3 + 0.5 + 1 / specs[animal][2]) + 3
        values[animal] = sum(samples) / len(samples) - cost - 4 * actions
    return values


def build():
    source = interaction("mixed_capacity")
    assert hashlib.sha256(source.encode()).hexdigest() == BASE_SHA256
    source = replace(source, "import math", "import math\nimport random")
    helpers = (
        inspect.getsource(animal_calendar) + "\n\n" + inspect.getsource(scenario_animal_values)
    )
    source = replace(source, "def agent(", helpers + "\n\ndef agent(")
    source = replace(
        source,
        "    # Investment is bounded",
        """    scenario_values = {}
    if 8 <= day <= p["animal_stop"] and cash > 450 and sum(stock[a] for a in ANIMALS) < 2 and len(animals) + sum(stock[a] for a in ANIMALS) < 18:
        scenario_values = scenario_animal_values(obs, ANIMALS, CROPS, SHOPS, inventory_quote, obs["market"].get("params") or default_price_parameters())

    # Investment is bounded""",
    )
    source = replace(
        source,
        "net = revenue - cost - feed_cost - (29 - day) * 12",
        "net = scenario_values.get(animal, revenue - cost - feed_cost - (29 - day) * 12)",
    )
    compile(source, "scenario_marginal", "exec")
    return source


def check():
    from copy import deepcopy

    from kaggle_environments.envs.kaggriculture import kaggriculture as game

    namespace = {}
    exec(build(), namespace)
    cases = 0
    for animal in namespace["ANIMALS"]:
        for placed in (0, 7, 9):
            tile = dict(
                animal=animal,
                placed_day=placed,
                kind=game.ANIMALS[animal]["structure"],
                yield_units=0,
                pending_care_bonus=2 if placed < 8 else 0,
                consecutive_unfed=0,
                fertilizer_available=False,
            )
            expected = animal_calendar(tile, 8, namespace["ANIMALS"])
            working = deepcopy(tile)
            observed = {item: [0.0] * 30 for item in expected}
            for day in range(max(8, placed), 28):
                working.update(fed_today=True, cared_today=True)
                game._daily_refresh_animals({"tiles": [[working]]}, day)
                observed[game.ANIMALS[animal]["product"]][day + 2] = working["yield_units"]
                working["yield_units"] = 0
                observed["FERTILIZER"][day + 2] = int(working["fertilizer_available"])
                working["fertilizer_available"] = False
                if day > 8 or placed > 8:
                    observed["WHEAT"][day] = -1
            assert observed == expected, (animal, placed, observed, expected)
            cases += 1
    quotes = 0
    for item, parameters in namespace["default_price_parameters"]().items():
        for inventory in range(9600, 10401, 7):
            assert namespace["inventory_quote"](inventory, parameters) == game.market_price(
                item, inventory
            )
            quotes += 1
    replay_path = next(Path("reports/replays/phase3-opening-field").glob("*cok*2009-0.json"))
    replay = json.loads(replay_path.read_bytes())
    runtimes = []
    rankings = []
    for day in range(8, 17):
        obs = replay["steps"][day * 24][0]["observation"]
        before = deepcopy(obs)
        start = time.perf_counter()
        values = scenario_animal_values(
            obs,
            namespace["ANIMALS"],
            namespace["CROPS"],
            namespace["SHOPS"],
            namespace["inventory_quote"],
            obs["market"].get("params") or namespace["default_price_parameters"](),
        )
        runtimes.append(time.perf_counter() - start)
        assert len(values) == 3 and before == obs
        rankings.append({"day": day, "values": values})
    return {
        "official_animal_calendar_cases": cases,
        "official_quote_cases": quotes,
        "observed_state_probes": len(runtimes),
        "maximum_seconds": max(runtimes),
        "rankings": rankings,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workers", type=int, default=3)
    parser.add_argument("--check-only", action="store_true")
    parser.add_argument("--output", type=Path, default=Path("data/raw/phase3-scenarios.json"))
    args = parser.parse_args()
    checks = check()
    print(json.dumps(checks), flush=True)
    if args.check_only:
        return
    content = build().encode()
    digest = hashlib.sha256(content).hexdigest()
    path = Path("data/interim/phase3-scenarios") / digest / "main.py"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
    opponents = [f"data/raw/reference-{name}/main.py" for name in ("seyam", "cok")]
    manifest = {
        **provenance([*opponents, __file__]),
        "candidate": str(path),
        "sha256": digest,
        "snapshot": snapshot(path),
        "name": "scenario_marginal",
        "base_sha256": BASE_SHA256,
        "complete": False,
        "seeds": [2000, 2003, 2009, 2013],
        "checks": checks,
        "episodes": [],
    }
    tasks = [
        (str(path), opponent, seed, seat, None)
        for opponent in opponents
        for seed in manifest["seeds"]
        for seat in (0, 1)
    ]
    with ProcessPoolExecutor(max_workers=args.workers) as pool:
        for row in pool.map(episode, tasks):
            manifest["episodes"].append(row)
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
            print(
                row["opponent"],
                row["seed"],
                row["seat"],
                row["cash"] - row["opponent_cash"],
                flush=True,
            )
    assert len(manifest["episodes"]) == len(tasks)
    assert hashlib.sha256(path.read_bytes()).hexdigest() == digest
    assert len({(e["opponent"], e["seed"], e["seat"]) for e in manifest["episodes"]}) == len(tasks)
    manifest["complete"] = True
    args.output.write_text(json.dumps(manifest, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
