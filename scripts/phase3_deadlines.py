"""Reserve feasible feed routes before imminent escape deadlines."""

import argparse
import gzip
import hashlib
import json
from concurrent.futures import ProcessPoolExecutor
from copy import deepcopy
from pathlib import Path

from benchmark import episode, provenance, snapshot
from phase2_logistics import replace

BASE = "febe9c76051a11e9ea7700e2d4701722e98274c51c50874ad03e1088b9398d4b"


def build(source=None):
    if source is None:
        raw = gzip.decompress((Path("reports/sources") / (BASE + ".py.gz")).read_bytes())
        assert hashlib.sha256(raw).hexdigest() == BASE
        source = raw.decode()
    source = replace(
        source,
        "    matched: dict[int, tuple[int, int]] = {}",
        r"""    # Reserve last-departure feed routes before ordinary task matching or DROP.
    # Feasibility includes acquiring feed and the action after arriving at the animal.
    deadline_actions = {}
    if day < 29:
        pending = {target for target, op, _, _, _ in tasks if op == "FEED"
                   and board[target[1]][target[0]]["consecutive_unfed"] > 0}
        all_carried = sum(sum(inv.values()) for inv in inventories)
        safe_nightly = sum(shed.values()) + all_carried <= cfg.get("shedCapacity", 100)
        while pending:
            candidates = []
            for target in pending:
                routes = []
                for i, pos in enumerate(positions):
                    if i in deadline_actions:
                        continue
                    inv = inventories[i]
                    sale_cargo = sum(n for item, n in inv.items() if item in BASE and item not in ("WHEAT", "FERTILIZER"))
                    if sale_cargo and (farm["money"] < 1000 or not safe_nightly):
                        continue
                    fetching = not inv.get("WHEAT", 0)
                    home = min(shed_tiles, key=lambda s: distance(pos, s) + distance(s, target))
                    if fetching:
                        if shed.get("WHEAT", 0) <= 0:
                            continue
                        cost = distance(pos, home) + 1 + distance(home, target) + 1
                    else:
                        cost = distance(pos, target) + 1
                    slack = 24 - hour - cost
                    if slack >= 0:
                        routes.append((cost, i, home, fetching, slack))
                if routes:
                    route = min(routes)
                    if route[-1] <= 3:
                        candidates.append((route[-1], target, route))
            if not candidates:
                break
            _, target, (_, i, home, fetching, _) = min(candidates)
            pos = positions[i]
            if fetching:
                # Reserve one shared unit even while the assigned worker walks.
                shed["WHEAT"] -= 1
                fetches["WHEAT"] += 1
                action = ["PICKUP", "WHEAT", 1] if pos == home else move(pos, home)
            else:
                action = ["FEED"] if pos == target else move(pos, target)
            deadline_actions[i] = action
            actions[i] = action
            claimed.add(target)
            pending.remove(target)
    matched: dict[int, tuple[int, int]] = {}""",
    )
    source = replace(
        source,
        "        for i, pos in enumerate(positions):\n            home = min(shed_tiles, key=lambda s: distance(pos, s))",
        "        for i, pos in enumerate(positions):\n            if i in deadline_actions:\n                continue\n            home = min(shed_tiles, key=lambda s: distance(pos, s))",
    )
    source = replace(
        source,
        "            for target, op, value, required_item, arg in tasks:\n",
        "            for target, op, value, required_item, arg in tasks:\n                if target in claimed:\n                    continue\n",
    )
    source = replace(
        source,
        "    for i in order:\n",
        "    for i in order:\n        if i in deadline_actions:\n            continue\n",
    )
    compile(source, "feed_deadlines", "exec")
    return source


def check():
    from kaggle_environments.envs.kaggriculture import kaggriculture as game

    replay = json.loads(
        next(Path("reports/replays/phase3-opening-field").glob("*cok*2009-0.json")).read_bytes()
    )
    ns = {"DEADLINES": []}
    source = build().replace(
        "            deadline_actions[i] = action",
        "            DEADLINES.append((target, i, action))\n            deadline_actions[i] = action",
    )
    exec(source, ns)
    checks = []
    for day, target in [(16, (9, 0)), (19, (7, 1))]:
        ns["DEADLINES"].clear()
        obs = deepcopy(replay["steps"][24 * day + 14][0]["observation"])
        action = ns["agent"](obs, replay["configuration"])
        pickups = [a for a in [action["farmer"], *action["hands"]] if a[:2] == ["PICKUP", "WHEAT"]]
        assert sum(a[2] for a in pickups) <= obs["private"]["shed"].get("WHEAT", 0)
        targets_assigned = [t for t, _, _ in ns["DEADLINES"]]
        assert len(targets_assigned) == len(set(targets_assigned))
        matches = [x for x in ns["DEADLINES"] if x[0] == target]
        assert matches, (day, ns["DEADLINES"])
        _, i, first = matches[0]
        assert [action["farmer"], *action["hands"]][i] == first
        farm = deepcopy(obs["farms"][0])
        private = deepcopy(obs["private"])
        game._apply_unit_action(farm, private, i, first, 10, day, 24, 100)
        assert private["inventories"][i].get("WHEAT", 0) > 0, (day, first)
        pos = [farm["farmer"], *farm["hands"]][i]
        route = []
        x, y = pos
        while x != target[0]:
            route.append(["EAST" if x < target[0] else "WEST"])
            x += 1 if x < target[0] else -1
        while y != target[1]:
            route.append(["SOUTH" if y < target[1] else "NORTH"])
            y += 1 if y < target[1] else -1
        route.append(["FEED"])
        assert 14 + 1 + len(route) <= 24
        for a in route:
            game._apply_unit_action(farm, private, i, a, 10, day, 24, 100)
        assert farm["tiles"][target[1]][target[0]]["fed_today"]
        game._daily_refresh_animals(farm, day)
        assert "animal" in farm["tiles"][target[1]][target[0]]
        checks.append(
            {
                "day": day,
                "target": target,
                "worker": i,
                "first_action": first,
                "feed_hour": 14 + len(route),
            }
        )
    return checks


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--workers", type=int, default=2)
    parser.add_argument("--output", type=Path, default=Path("data/raw/phase3-deadlines.json"))
    args = parser.parse_args()
    checks = check()
    if args.check:
        print(json.dumps(checks, indent=2))
        return
    content = build().encode()
    digest = hashlib.sha256(content).hexdigest()
    path = Path("data/interim/phase3-deadlines") / digest / "main.py"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
    opponents = ["data/raw/reference-cok/main.py", "data/raw/reference-seyam/main.py"]
    manifest = {
        **provenance([str(path), *opponents]),
        "base_sha256": BASE,
        "hypothesis": "Reserve feasible imminent escape feed routes before delivery and ordinary tasks",
        "candidate_snapshot": snapshot(path),
        "contract_checks": checks,
        "complete": False,
        "episodes": [],
    }
    tasks = [
        (str(path), opp, seed, seat, "reports/replays/phase3-deadlines" if seed == 2009 else None)
        for opp in opponents
        for seed in [2000, 2003, 2009, 2013]
        for seat in (0, 1)
    ]
    with ProcessPoolExecutor(max_workers=args.workers) as pool:
        for row in pool.map(episode, tasks):
            manifest["episodes"].append(row)
            args.output.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
            print(
                row["opponent"],
                row["seed"],
                row["seat"],
                row["cash"],
                row["opponent_cash"],
                flush=True,
            )
    manifest["complete"] = True
    args.output.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
