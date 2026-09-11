"""Experimental animal service routes built over the immutable v8 policy.

A worker commits to several adjacent animals, reserves every required wheat,
and acknowledges work from the next observation. The route accounts for pickup,
travel and all service actions before claiming a worker. It uses current public
and private observations only; no reference schedules or future states.
"""

from __future__ import annotations

import gzip
import hashlib
import inspect
import sys
import time
from collections import Counter
from pathlib import Path

from kaggriculture.agent.competitive import PARAMS, distance, move

INCUMBENT = "64fe323936dc9494add413eb956b0294658a88efe28572332c94676c68a09325"
_SERVICE_STATE = {}
_SERVICE_DIAGNOSTICS = Counter()


def service_routes(obs, cfg, positions, inventories, shed, tasks, shed_tiles):
    """Reserve complete, feasible local service routes and emit their next actions.

    Route state is a disposable execution aid: every operation is checked against
    the observed tile and inventory, and new days/nonconsecutive observations
    discard commitments. The rest of the farm retains the incumbent scheduler.
    """
    player, day, hour, step = obs["player"], obs["day"], obs["hour"], obs["step"]
    farm = obs["farms"][player]
    board = farm["tiles"]
    state = _SERVICE_STATE.get(player)
    if not state or state["day"] != day or step not in (state["step"], state["step"] + 1):
        state = {"day": day, "step": step, "plans": {}}
        _SERVICE_STATE[player] = state
    if step == 0:
        state["plans"] = {}
    state["step"] = step
    if day >= 29:
        state["plans"] = {}
        return {}, set()

    plans = state["plans"]
    deadline = time.perf_counter() + 0.05
    capacity = cfg.get("shedCapacity", 100)
    access = set(shed_tiles)

    def identity(target):
        tile = board[target[1]][target[0]]
        if isinstance(tile, dict) and "animal" in tile:
            return tile["animal"], tile["placed_day"]
        return None

    def pending(operation):
        target, op, cohort = operation
        if op == "DROP":
            return True
        if identity(target) != cohort:
            return False
        tile = board[target[1]][target[0]]
        return {
            "FEED": not tile["fed_today"],
            "CARE": not tile["cared_today"],
            "HARVEST": tile["yield_units"] > 0,
            "COLLECT_FERTILIZER": tile["fertilizer_available"],
        }[op]

    def route_cost(pos, operations, wheat):
        need = sum(op == "FEED" for _, op, _ in operations)
        missing = max(0, need - wheat)
        total = 0
        if missing:
            home = min(access, key=lambda h: (distance(pos, h) + distance(h, operations[0][0]), h))
            total += distance(pos, home) + 1
            pos = home
        else:
            home = None
        for target, _, _ in operations:
            total += distance(pos, target) + 1
            pos = target
        return total, missing, home

    # Persist only obligations that are still present. A moved/replaced animal,
    # disappearing worker, or impossible remaining route releases its capacity.
    for worker in list(plans):
        plan = plans[worker]
        if worker >= len(positions):
            del plans[worker]
            continue
        operations = [operation for operation in plan["ops"] if pending(operation)]
        if operations and operations[0][1] == "DROP" and not inventories[worker]:
            operations = []
        if not operations:
            del plans[worker]
            continue
        plan["ops"] = operations
        cost, _, _ = route_cost(positions[worker], operations, inventories[worker].get("WHEAT", 0))
        if hour + cost > 24:
            del plans[worker]

    claimed = {target for plan in plans.values() for target, op, _ in plan["ops"] if op != "DROP"}
    available = shed.get("WHEAT", 0)
    # Reserve walking workers' pickup obligations too, not just today's PICKUP.
    for worker in sorted(list(plans)):
        plan = plans[worker]
        _, missing, _ = route_cost(
            positions[worker], plan["ops"], inventories[worker].get("WHEAT", 0)
        )
        if missing > available:
            _SERVICE_DIAGNOSTICS["input_invalidations"] += 1
            del plans[worker]
        else:
            available -= missing
    claimed = {target for plan in plans.values() for target, op, _ in plan["ops"] if op != "DROP"}

    task_map = {}
    for target, op, value, _, _ in tasks:
        if identity(target) and target not in claimed:
            task_map.setdefault(target, {})[op] = value
    stops = {}
    for target, values in task_map.items():
        tile = board[target[1]][target[0]]
        operations, reward = [], 0
        for op in ("FEED", "HARVEST", "CARE", "COLLECT_FERTILIZER"):
            value = values.get(op, 0)
            # CARE is allowed by the interpreter before feeding, but earns a
            # bonus only on a fed day. Include it after a route's FEED action.
            if op == "CARE" and "FEED" in values and not tile["cared_today"] and PARAMS["care"]:
                value = 60
            # Today's care enters the bonus bank after production, so day-28
            # care cannot increase any product available for the final sale.
            if op == "CARE" and day >= 28:
                value = 0
            if value:
                operations.append((target, op, identity(target)))
                reward += value
        if operations:
            stops[target] = (operations, reward)

    # Full routes compete against the best currently executable ordinary task.
    # At most half the workers commit; crops and new investments keep capacity.
    limit = max(1, len(positions) // 2)
    while len(plans) < limit and stops and time.perf_counter() < deadline:
        best = None
        for worker, pos in enumerate(positions):
            if worker in plans:
                continue
            ordinary = 0
            for target, _, value, required, _ in tasks:
                if target in claimed or identity(target):
                    continue
                cost = distance(pos, target) + 1
                if required and not inventories[worker].get(required, 0):
                    if not shed.get(required, 0):
                        continue
                    cost = min(distance(pos, home) + distance(home, target) + 2 for home in access)
                ordinary = max(ordinary, value / (cost + 1.5))
            starts = sorted(stops, key=lambda target: (distance(pos, target), target))[:4]
            for start in starts:
                if time.perf_counter() >= deadline:
                    break
                route, reward = [], 0
                targets, current = [], start
                for _ in range(3):
                    added, value = stops[current]
                    route = route + added
                    reward += value
                    targets.append(current)
                    cost, missing, _ = route_cost(pos, route, inventories[worker].get("WHEAT", 0))
                    if missing > available or hour + cost > 24:
                        break
                    if len(route) >= 2:
                        score = reward / (cost + 1.5)
                        # A complete service circuit must repay displaced work.
                        if score >= ordinary:
                            item = (score, reward, -worker, tuple(targets), list(route), missing)
                            if best is None or item[:4] > best[:4]:
                                best = item
                    remaining = [
                        target
                        for target in stops
                        if target not in targets and distance(current, target) <= 3
                    ]
                    if not remaining:
                        break
                    current = max(
                        remaining,
                        key=lambda target: (
                            stops[target][1] / (distance(current, target) + len(stops[target][0])),
                            target,
                        ),
                    )
        if best is None:
            break
        _, _, negative_worker, targets, operations, missing = best
        worker = -negative_worker
        # Nightly delivery is free when capacity and working capital allow it.
        # Otherwise include a real delivery in the route's feasibility budget.
        collected = sum(
            board[target[1]][target[0]]["yield_units"]
            if op == "HARVEST"
            else int(op == "COLLECT_FERTILIZER")
            for target, op, _ in operations
        )
        feeds = sum(op == "FEED" for _, op, _ in operations)
        cargo = (
            sum(inventories[worker].values())
            + collected
            - min(inventories[worker].get("WHEAT", 0), feeds)
        )
        night_load = (
            sum(shed.values()) + sum(sum(inv.values()) for inv in inventories) + collected - feeds
        )
        if cargo and (farm["money"] < 1000 or night_load > capacity):
            home = min(access, key=lambda h: (distance(operations[-1][0], h), h))
            delivered = [*operations, (home, "DROP", None)]
            cost, _, _ = route_cost(
                positions[worker], delivered, inventories[worker].get("WHEAT", 0)
            )
            if hour + cost <= 24 and cargo <= capacity - sum(shed.values()):
                operations = delivered
            else:
                # Do not claim a cash-producing route with no safe delivery.
                for target in targets:
                    stops.pop(target)
                continue
        plans[worker] = {"ops": operations}
        available -= missing
        for target in targets:
            claimed.add(target)
            stops.pop(target)

    result = {}
    if time.perf_counter() >= deadline:
        _SERVICE_DIAGNOSTICS["budget_exhaustions"] += 1
        print("service_route_budget_fallback", file=sys.stderr)
    for worker in sorted(list(plans)):
        operations = plans[worker]["ops"]
        pos = positions[worker]
        cost, missing, home = route_cost(pos, operations, inventories[worker].get("WHEAT", 0))
        if missing:
            result[worker] = ["PICKUP", "WHEAT", missing] if pos == home else move(pos, home)
        else:
            target, op, _ = operations[0]
            if op == "DROP" and sum(inventories[worker].values()) > capacity - sum(shed.values()):
                del plans[worker]
                continue
            result[worker] = [op] if pos == target else move(pos, target)
        _SERVICE_DIAGNOSTICS["committed_actions"] += 1
    shed["WHEAT"] = available
    return result, claimed


def build():
    """Return a deterministic standalone candidate; never edit the incumbent."""
    root = Path(__file__).resolve().parents[1]
    raw = gzip.decompress((root / "reports/sources" / f"{INCUMBENT}.py.gz").read_bytes())
    assert hashlib.sha256(raw).hexdigest() == INCUMBENT
    source = raw.decode()
    marker = "    deadline_actions = {}\n    if day < 29:"
    replacement = """    deadline_actions, route_claimed = service_routes(
        obs, cfg, positions, inventories, shed, tasks, shed_tiles
    )
    claimed.update(route_claimed)
    for worker, action in deadline_actions.items():
        actions[worker] = action
    if day < 29:"""
    assert source.count(marker) == 1
    source = source.replace(marker, replacement)
    source = source.replace(
        'if op == "FEED" and board[target[1]][target[0]]["consecutive_unfed"] > 0',
        'if op == "FEED" and target not in claimed and board[target[1]][target[0]]["consecutive_unfed"] > 0',
    )
    helpers = "_SERVICE_STATE = {}\n_SERVICE_DIAGNOSTICS = Counter()\n\n"
    helpers += inspect.getsource(service_routes) + "\n\n"
    # kaggle-environments selects the last callable defined in source.
    # Keep the deployment entry point last, including in clean-directory runs.
    assert source.count("def agent(") == 1
    source = source.replace("def agent(", helpers + "def agent(")
    source = source.replace(
        '"""Pure observation policy: no episode globals or repository imports."""',
        '"""Observation policy with disposable, validated local service commitments."""',
    )
    compile(source, "service_routes_candidate", "exec")
    return source


if __name__ == "__main__":
    artifact = build()
    print(hashlib.sha256(artifact.encode()).hexdigest())
