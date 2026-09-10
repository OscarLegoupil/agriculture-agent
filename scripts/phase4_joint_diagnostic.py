"""Exact bounded maintenance assignment on known replay observations; no games."""

import argparse
import gzip
import hashlib
import itertools
import json
import sys
from collections import deque
from copy import deepcopy
from functools import cache
from pathlib import Path

from kaggle_environments.envs.kaggriculture import kaggriculture as game

BANKED = "401b58a64d12a3df82ae9157a8d12a0d1e99c10c273fecb96f0d399501a9c6d4"


def audit_banked(observation, configuration):
    raw = gzip.decompress((Path("reports/sources") / f"{BANKED}.py.gz").read_bytes())
    assert hashlib.sha256(raw).hexdigest() == BANKED
    namespace = {}
    exec(compile(raw, BANKED, "exec"), namespace)
    details = {"source_sha256": BANKED}

    def capture(frame, event, _arg):
        if event == "return" and frame.f_code is namespace["agent"].__code__:
            for key in (
                "safe_nightly",
                "all_carried",
                "valuable_production",
                "pending",
                "deadline_actions",
            ):
                value = frame.f_locals.get(key)
                details[key] = sorted(value) if isinstance(value, set) else deepcopy(value)

    previous = sys.getprofile()
    try:
        sys.setprofile(capture)
        details["actions"] = namespace["agent"](deepcopy(observation), configuration)
    finally:
        sys.setprofile(previous)
    return details


@cache
def path(start, target, size):
    """Official movement allows every in-board cell, including locked quadrants."""
    queue = deque([(start, ())])
    seen = {start}
    while queue:
        position, actions = queue.popleft()
        if position == target:
            return actions
        for direction, (dx, dy) in game.FARMER_MOVES.items():
            neighbor = position[0] + dx, position[1] + dy
            if min(neighbor) >= 0 and max(neighbor) < size and neighbor not in seen:
                seen.add(neighbor)
                queue.append((neighbor, (*actions, (direction,))))
    raise ValueError("Unreachable board coordinate")


def tasks_for(farm, day):
    """Select only observable crop survival and immediate feeding obligations."""
    tasks = []
    for y, row in enumerate(farm["tiles"]):
        for x, tile in enumerate(row):
            if not isinstance(tile, dict):
                continue
            if "crop" in tile and not tile["watered_today"] and tile["consecutive_unwatered"]:
                tasks.append({"position": (x, y), "action": "WATER", "extra_units": 0})
            if "animal" not in tile or tile["fed_today"]:
                continue
            outputs = []
            for fed in (False, True):
                probe = game._new_farm(10, 3000)
                probe["tiles"][y][x] = deepcopy(tile)
                probe["tiles"][y][x]["fed_today"] = fed
                game._daily_refresh_animals(probe, day)
                outputs.append(probe["tiles"][y][x].get("yield_units", 0))
            if outputs[1] > outputs[0] or tile["consecutive_unfed"]:
                tasks.append(
                    {"position": (x, y), "action": "FEED", "extra_units": outputs[1] - outputs[0]}
                )
    if len(tasks) > 8:
        raise ValueError("More than eight obligations: do not silently discard urgent tasks")
    return tasks


def worker_routes(position, carried, available, tasks, horizon, size):
    """All task orders and one optional depot pickup; retain cheapest subset route."""
    half = size // 2
    depots = [(x, y) for x in (half - 1, half) for y in (half - 1, half)]
    best = {(0, 0): ()}
    for count in range(1, len(tasks) + 1):
        for order in itertools.permutations(range(len(tasks)), count):
            needed = max(0, sum(tasks[i]["action"] == "FEED" for i in order) - carried)
            if needed > available:
                continue
            insertions = range(count + 1) if needed else (None,)
            for insertion in insertions:
                for depot in depots if needed else (None,):
                    current, feed, actions = position, carried, []
                    valid = True
                    for j in range(count + 1):
                        if j == insertion:
                            actions.extend(path(current, depot, size))
                            actions.append(("PICKUP", "WHEAT", needed))
                            current, feed = depot, feed + needed
                        if j == count:
                            break
                        task = tasks[order[j]]
                        actions.extend(path(current, task["position"], size))
                        actions.append((task["action"],))
                        current = task["position"]
                        feed -= task["action"] == "FEED"
                        if feed < 0 or len(actions) > horizon:
                            valid = False
                            break
                    key = sum(1 << i for i in order), needed
                    if (
                        valid
                        and len(actions) <= horizon
                        and len(actions) < len(best.get(key, (0,) * 999))
                    ):
                        best[key] = tuple(actions)
    return best


def solve(farm, private, tasks, horizon):
    workers = [farm["farmer"], *farm["hands"]]
    available = private["shed"].get("WHEAT", 0)
    states = {(0, 0): (0, {})}
    for worker, position in enumerate(workers):
        options = worker_routes(
            tuple(position),
            private["inventories"][worker].get("WHEAT", 0),
            available,
            tasks,
            horizon,
            len(farm["tiles"]),
        )
        updated = dict(states)
        for (mask, used), (cost, schedules) in states.items():
            for (extra, pickup), actions in options.items():
                if extra & mask or used + pickup > available:
                    continue
                key = mask | extra, used + pickup
                proposal = cost + len(actions)
                if key not in updated or proposal < updated[key][0]:
                    updated[key] = proposal, {**schedules, worker: actions}
        states = updated
    full = (1 << len(tasks)) - 1
    feasible = [(v[0], k[1], v[1]) for k, v in states.items() if k[0] == full]
    return min(feasible, key=lambda row: row[:2]) if feasible else None


def diagnose(replay, seed, day, hour):
    steps = replay["steps"]
    index = next(
        i
        for i, s in enumerate(steps)
        if s[0]["observation"]["day"] == day and s[0]["observation"]["hour"] == hour
    )
    observation = steps[index][0]["observation"]
    farm, private = deepcopy(observation["farms"][0]), deepcopy(observation["private"])
    tasks = tasks_for(farm, day)
    solution = solve(farm, private, tasks, 24 - hour)
    result = {
        "seed": seed,
        "seat": 0,
        "day": day,
        "hour": hour,
        "tasks": tasks,
        "shed_wheat": private["shed"].get("WHEAT", 0),
        "workers": [farm["farmer"], *farm["hands"]],
        "carried_wheat": [v.get("WHEAT", 0) for v in private["inventories"]],
        "feasible": solution is not None,
        "banked_policy_audit": audit_banked(observation, replay["configuration"]),
        "recorded_next_action": steps[index + 1][0].get("action"),
    }
    if solution is None:
        return result
    cost, pickup, schedules = solution
    # Isolate the selected obligations. Other workers PASS: no unobserved purchases,
    # future harvesting, hires, deposits or opponent actions finance this rescue.
    for offset in range(24 - hour):
        for worker, actions in schedules.items():
            action = actions[offset] if offset < len(actions) else ("PASS",)
            game._apply_unit_action(farm, private, worker, list(action), 10, day, 24, 100)
    for task in tasks:
        x, y = task["position"]
        flag = "fed_today" if task["action"] == "FEED" else "watered_today"
        assert farm["tiles"][y][x][flag], (task, schedules)
    refreshed = deepcopy(farm)
    game._daily_refresh_plants(refreshed, day, 24)
    game._daily_refresh_animals(refreshed, day)
    for task in tasks:
        x, y = task["position"]
        assert refreshed["tiles"][y][x]["kind"] != "WEED"
    baseline_next = steps[index + 24 - hour][0]["observation"]["farms"][0]
    extra_products = {}
    for task in tasks:
        if task["action"] != "FEED":
            continue
        x, y = task["position"]
        tile = refreshed["tiles"][y][x]
        product = game.ANIMALS[tile["animal"]]["product"]
        extra_products[product] = extra_products.get(product, 0) + (
            tile["yield_units"] - baseline_next["tiles"][y][x].get("yield_units", 0)
        )
    displaced = {}
    for worker in schedules:
        displaced[worker] = []
        for offset in range(24 - hour):
            original = steps[index + offset + 1][0].get("action") or {}
            actions = [original.get("farmer", ["PASS"]), *original.get("hands", [])]
            displaced[worker].append(actions[worker] if worker < len(actions) else ["PASS"])
    result.update(
        {
            "total_worker_actions": cost,
            "depot_wheat_used": pickup,
            "schedules": schedules,
            "official_obligation_checks_passed": True,
            "banked_units_protected_against_no_service": sum(t["extra_units"] for t in tasks),
            "held_product_difference_vs_recorded_next_morning": extra_products,
            "current_quote_gross_upper_bound": sum(
                quantity * observation["market"]["prices"][product]
                for product, quantity in extra_products.items()
            ),
            "wheat_quote": observation["market"]["prices"]["WHEAT"],
            "displaced_recorded_actions_offline_only": displaced,
            "urgent_crops_preserved": sum(t["action"] == "WATER" for t in tasks),
        }
    )
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--replays", type=Path, default=Path("reports/replays/phase4-losses"))
    parser.add_argument(
        "--output", type=Path, default=Path("reports/results/phase4-joint-diagnostic.json")
    )
    args = parser.parse_args()
    cases, inputs = [], []
    for seed, day, hours in [(3029, 8, (16, 18, 20)), (3063, 11, (16, 18, 20))]:
        source = next(args.replays.glob(f"*-{seed}-0.json"))
        raw = source.read_bytes()
        inputs.append({"path": source.as_posix(), "sha256": hashlib.sha256(raw).hexdigest()})
        replay = json.loads(raw)
        cases.extend(diagnose(replay, seed, day, hour) for hour in hours)
    result = {
        "complete": True,
        "scope": "offline selected-state feasibility, not match outcomes",
        "route_model": "exact subset partition; at most one depot pickup per worker; no transfers",
        "inputs": inputs,
        "interpreter_sha256": hashlib.sha256(Path(game.__file__).read_bytes()).hexdigest(),
        "cases": cases,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(cases, indent=2))


if __name__ == "__main__":
    main()
