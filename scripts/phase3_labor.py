"""Daily marginal hiring from remaining jobs and greedy service routes."""

import argparse
import hashlib
import inspect
import json
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

from benchmark import episode, provenance, snapshot
from phase2_logistics import replace
from phase3_startup import build as startup


def labor_route_value(jobs, positions, homes, remaining, extra, slack):
    positions = [tuple(p) for p in positions]
    for _ in range(extra):
        positions.append(min(homes, key=lambda p: (positions.count(p), homes.index(p))))
    times = [0.0] * (len(positions) - extra) + [1.0] * extra
    value = 0.0
    for target, work, benefit, deadline, _urgent in sorted(
        jobs, key=lambda j: (-j[4], j[3], -j[2] / max(1, j[1]))
    ):
        options = []
        for worker, pos in enumerate(positions):
            finish = times[worker] + abs(pos[0] - target[0]) + abs(pos[1] - target[1]) + work
            if finish <= min(deadline, remaining * slack):
                options.append((finish, worker))
        if options:
            finish, worker = min(options)
            positions[worker] = target
            times[worker] = finish
            value += benefit
    return value


def marginal_labor(
    obs, params, crop_specs, animal_specs, forecast, purchase, slack=0.8, cash_reserve=150
):
    farm = obs["farms"][obs["player"]]
    private = obs["private"]
    day, hour = obs["day"], obs["hour"]
    half = len(farm["tiles"]) // 2
    homes = [(half - 1, half - 1), (half, half - 1), (half - 1, half), (half, half)]
    positions = [farm["farmer"], *farm["hands"]]
    remaining = (23 if day == 29 else 24) - hour
    stock = dict(private["shed"])
    for inventory in private["inventories"]:
        for item, count in inventory.items():
            stock[item] = stock.get(item, 0) + count
    jobs, free = [], []
    plant_count = 0
    feed_need = 0
    for y, row in enumerate(farm["tiles"]):
        for x, tile in enumerate(row):
            if tile == "LOCKED":
                continue
            target = (x, y)
            home_distance = min(abs(x - h[0]) + abs(y - h[1]) for h in homes)
            if tile is None or (
                isinstance(tile, dict)
                and tile.get("kind") in ("WEED", "COOP", "PASTURE")
                and "animal" not in tile
            ):
                free.append((home_distance, target, tile is not None))
                continue
            work = benefit = urgent = 0.0
            deadline = remaining
            if "animal" in tile:
                cost, first, interval, cap, product, _ = animal_specs[tile["animal"]]
                age = day - tile["placed_day"]
                next_production = (
                    day + max(1, first - age)
                    if age < first
                    else day + interval - (age - first) % interval
                )
                useful = next_production <= 29 or tile["yield_units"] > 0
                if not tile["fed_today"] and useful and day < 29:
                    feed_need += 1
                    work += 1 + (1 + 2 * home_distance) / 3
                    benefit += cost if tile["consecutive_unfed"] else max(30, forecast[product])
                    urgent = 2 if tile["consecutive_unfed"] else 1
                if params["care"] and not tile["cared_today"] and useful and day < 29:
                    work += 1
                    benefit += forecast[product]
                if tile["yield_units"]:
                    work += 1 + tile["yield_units"] / 5 * (home_distance + 1)
                    benefit += tile["yield_units"] * forecast[product]
                if tile["fertilizer_available"] and day < 29:
                    work += 1 + (home_distance + 1) / 5
                    benefit += obs["market"]["prices"]["FERTILIZER"]
            elif tile.get("kind") == "PLANT":
                plant_count += 1
                crop = tile["crop"]
                _, first, last, interval, cap = crop_specs[crop]
                age = day - tile["planted_day"]
                growth = (
                    ((last + 1) // 2 <= age <= last)
                    if not interval
                    else (
                        age + 1 >= first
                        and (age + 1 - first) % interval == 0
                        and (age + 1 - first) // interval < cap
                    )
                )
                exhausted = (
                    interval and age >= first + (cap - 1) * interval and not tile["yield_units"]
                )
                if exhausted:
                    if day < 27:
                        jobs.append((target, 1, 30, deadline, 0))
                    continue
                if (
                    not tile["watered_today"]
                    and day < 29
                    and (tile["consecutive_unwatered"] or growth)
                ):
                    work += 1
                    benefit += max(30, forecast[crop] * (2 if tile["consecutive_unwatered"] else 1))
                    urgent = 2 if tile["consecutive_unwatered"] else 1
                desired = 2 if interval else min(cap, 1 + last - (last + 1) // 2 + 1)
                if (
                    age >= first
                    and tile["yield_units"]
                    and (
                        tile["yield_units"] >= desired
                        or day == 29
                        or (
                            tile["max_lifespan_step"] <= obs["step"] + 24
                            and tile["max_lifespan_step"] >= 0
                        )
                    )
                ):
                    work += 1 + tile["yield_units"] / 5 * (home_distance + 1)
                    benefit += tile["yield_units"] * forecast[crop]
                    if tile["max_lifespan_step"] >= 0:
                        deadline = min(deadline, max(2, tile["max_lifespan_step"] - obs["step"]))
                if (
                    interval
                    and params["fertilize"]
                    and growth
                    and day < 29
                    and tile["fertilized_until_day"] < day
                    and forecast[crop] > obs["market"]["prices"]["FERTILIZER"] * 0.7 + 10
                ):
                    work += 1 + (1 + 2 * home_distance) / 4
                    benefit += max(0, forecast[crop] - obs["market"]["prices"]["FERTILIZER"])
            if work:
                jobs.append((target, work, benefit, deadline, urgent))
    feed_cost = max(0, feed_need - stock.get("WHEAT", 0)) * (obs["market"]["prices"]["WHEAT"] + 1)
    working_cash = max(0, farm["money"] - min(feed_cost, farm["money"]) - cash_reserve)
    pending = sum(stock.get(animal, 0) for animal in animal_specs) + bool(purchase)
    sowings = min(
        max(0, params["crop_tiles"] - plant_count),
        sum(private["seeds"].values()) + int(working_cash // (40 if day < 3 else 100)),
        12,
    )
    for home_distance, target, occupied in sorted(free):
        if pending:
            jobs.append((target, 3 + bool(occupied) + home_distance, 120, remaining, 0))
            pending -= 1
        elif sowings and day < 27:
            jobs.append((target, 2 + bool(occupied), 75, remaining, 0))
            sowings -= 1
    # The farmer is free; new hands become usable on the next action only.
    current = len(farm["hands"])
    target = current
    previous_value = labor_route_value(jobs, positions, homes, remaining, 0, slack)
    costs = []
    a, b = 1, 1
    for _ in range(params["hands"]):
        costs.append(a)
        a, b = b, a + b
    spent = 0
    for hands in range(current + 1, params["hands"] + 1):
        spent += costs[hands - 1]
        value = labor_route_value(jobs, positions, homes, remaining, hands - current, slack)
        if spent <= working_cash and value - previous_value > costs[hands - 1]:
            target = hands
        previous_value = value
    # Preserve the original opening's minimum crew for unobserved purchases.
    return min(params["hands"], max(target, 6 if day < 2 else current))


def build(slack=0.8, cash_reserve=150):
    source = startup("startup_fert_reserve")
    helper = inspect.getsource(labor_route_value) + "\n\n" + inspect.getsource(marginal_labor)
    source = replace(source, "def agent(", helper + "\n\ndef agent(")
    start = source.index("    workload = max(48")
    end = source.index("    if hour < 8:", start)
    source = (
        source[:start]
        + f"    target_hands = marginal_labor(obs, p, CROPS, ANIMALS, forecast, purchase, slack={slack}, cash_reserve={cash_reserve})\n"
        + source[end:]
    )
    return source


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--slack", type=float, default=0.8)
    parser.add_argument("--cash-reserve", type=int, default=150)
    parser.add_argument("--workers", type=int, default=2)
    args = parser.parse_args()
    base_content = startup("startup_fert_reserve").encode()
    content = build(args.slack, args.cash_reserve).encode()
    digest = hashlib.sha256(content).hexdigest()
    path = Path("data/interim/phase3-labor") / digest / "main.py"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
    opponents = ["data/raw/reference-seyam/main.py", "data/raw/reference-cok/main.py"]
    manifest = {
        **provenance([*opponents]),
        "base_sha256": hashlib.sha256(base_content).hexdigest(),
        "candidate": str(path),
        "sha256": digest,
        "snapshot": snapshot(path),
        "capacity_fraction": args.slack,
        "cash_reserve": args.cash_reserve,
        "complete": False,
        "episodes": [],
    }
    output = Path(f"data/interim/phase3-labor/results-{args.slack}-{args.cash_reserve}.json")
    tasks = [
        (str(path), opponent, seed, seat, None)
        for opponent in opponents
        for seed in (0, 2001)
        for seat in (0, 1)
    ]
    with ProcessPoolExecutor(max_workers=args.workers) as pool:
        for row in pool.map(episode, tasks):
            manifest["episodes"].append(row)
            output.write_text(json.dumps(manifest, indent=2))
            print(
                row["opponent"],
                row["seed"],
                row["seat"],
                row["cash"] - row["opponent_cash"],
                flush=True,
            )
    assert hashlib.sha256(path.read_bytes()).hexdigest() == digest
    assert len(manifest["episodes"]) == len(tasks)
    assert len({(r["opponent"], r["seed"], r["seat"]) for r in manifest["episodes"]}) == len(tasks)
    manifest["completion_verification"] = {
        "expected_games": len(tasks),
        "candidate_sha256_verified": True,
        "all_statuses_done": all(
            all(s == "DONE" for s in r["statuses"]) for r in manifest["episodes"]
        ),
    }
    manifest["complete"] = True
    output.write_text(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
