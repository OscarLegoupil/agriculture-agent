"""Read saved severe losses and probe avoidable idle actions with official work."""

import argparse
import gzip
import hashlib
import json
import sys
from collections import Counter
from copy import deepcopy
from pathlib import Path

from kaggle_environments.envs.kaggriculture import kaggriculture as game

BASE = "64fe323936dc9494add413eb956b0294658a88efe28572332c94676c68a09325"


def route_metrics(replay):
    segments, counts, witnesses = {}, Counter(), []
    for index, (before, after) in enumerate(
        zip(replay["steps"], replay["steps"][1:], strict=False)
    ):
        obs = before[0]["observation"]
        if obs["hour"] == 0:
            segments = {}
        farm = obs["farms"][0]
        decision = after[0].get("action") or {}
        actions = [decision.get("farmer", ["PASS"]), *decision.get("hands", [])]
        for worker, position in enumerate([farm["farmer"], *farm["hands"]]):
            start, moves, start_index = segments.get(worker, (position, 0, index))
            op = actions[worker][0] if worker < len(actions) else "PASS"
            if op in game.FARMER_MOVES:
                segments[worker] = start, moves + 1, start_index
            elif op != "PASS":
                shortest = abs(start[0] - position[0]) + abs(start[1] - position[1])
                counts["excess_moves_between_work"] += moves - shortest
                counts["work_segments"] += 1
                if op == "DROP" and moves - shortest >= 4:
                    original = replay["steps"][start_index][0]["observation"]
                    trial_farm, trial_private = (
                        deepcopy(original["farms"][0]),
                        deepcopy(original["private"]),
                    )
                    from phase4_joint_diagnostic import path

                    compact = [*path(tuple(start), tuple(position), 10), ("DROP",)]
                    initial = deepcopy(trial_private["inventories"][worker])
                    for action in compact:
                        game._apply_unit_action(
                            trial_farm,
                            trial_private,
                            worker,
                            list(action),
                            10,
                            original["day"],
                            24,
                            100,
                        )
                    delivered = Counter(trial_private["shed"]) - Counter(
                        original["private"]["shed"]
                    )
                    assert sum(delivered.values()) == sum(initial.values())
                    witnesses.append(
                        {
                            "day": obs["day"],
                            "start_hour": original["hour"],
                            "worker": worker,
                            "start": start,
                            "end": position,
                            "original_moves": moves,
                            "shortest_moves": shortest,
                            "actions": compact,
                            "official_delivered": dict(delivered),
                        }
                    )
                segments[worker] = position, 0, index + 1
    return {"counts": counts, "drop_witnesses_offline_selected": witnesses}


def analyse(path):
    raw = path.read_bytes()
    replay = json.loads(raw)
    source = gzip.decompress((Path("reports/sources") / f"{BASE}.py.gz").read_bytes())
    assert hashlib.sha256(source).hexdigest() == BASE
    namespace = {}
    exec(source, namespace)
    captures = {}

    def profile(frame, event, _argument):
        if event == "return" and frame.f_code is namespace["agent"].__code__:
            for key in ("matched", "tasks", "deadline_actions"):
                captures[key] = deepcopy(frame.f_locals.get(key))

    counts = Counter()
    events = []
    for before, after in zip(replay["steps"], replay["steps"][1:], strict=False):
        obs = before[0]["observation"]
        day, hour = obs["day"], obs["hour"]
        farm, private = deepcopy(obs["farms"][0]), deepcopy(obs["private"])
        original = after[0].get("action") or {}
        positions = [farm["farmer"], *farm["hands"]]
        actions = [original.get("farmer", ["PASS"]), *original.get("hands", [])]
        actions.extend([["PASS"]] * (len(positions) - len(actions)))
        old_profile = sys.getprofile()
        try:
            sys.setprofile(profile)
            regenerated = namespace["agent"](deepcopy(obs), replay["configuration"])
        finally:
            sys.setprofile(old_profile)
        counts["regenerated_action_mismatches"] += regenerated != original
        matched = captures["matched"]
        if regenerated == original:
            for worker, target in matched.items():
                if actions[worker][0] == "DROP":
                    counts["matched_worker_dropped"] += 1
                    counts["remote_target_orphaned_by_drop"] += tuple(positions[worker]) != target
        proposed = Counter(a[1] for a in actions if len(a) > 1 and a[0] == "PLANT")
        blocked = {crop for crop, n in proposed.items() if n > private["seeds"].get(crop, 0)}
        for worker, action in enumerate(actions):
            if action[0] == "PLANT" and action[1] in blocked:
                action = ["PASS"]
            if action[0] == "PASS" and day < 29:
                counts["nonterminal_pass"] += 1
                x, y = [farm["farmer"], *farm["hands"]][worker]
                alternatives = []
                for op in ("COLLECT_FERTILIZER", "CARE", "WATER", "FEED"):
                    trial_farm, trial_private = deepcopy(farm), deepcopy(private)
                    tile = deepcopy(farm["tiles"][y][x])
                    game._apply_unit_action(
                        trial_farm, trial_private, worker, [op], 10, day, 24, 100
                    )
                    if (trial_farm, trial_private) == (farm, private):
                        continue
                    # Do not credit maintenance that a later indexed worker already performs.
                    later_duplicates = any(
                        next_action[0] == op and positions[j] == [x, y]
                        for j, next_action in enumerate(actions)
                        if j > worker
                    )
                    if later_duplicates:
                        continue
                    detail = {"operation": op, "tile": tile}
                    if op == "COLLECT_FERTILIZER":
                        detail["units"] = trial_private["inventories"][worker].get(
                            "FERTILIZER", 0
                        ) - private["inventories"][worker].get("FERTILIZER", 0)
                        detail["quote_upper_bound"] = (
                            detail["units"] * obs["market"]["prices"]["FERTILIZER"]
                        )
                        detail["current_nightly_room"] = (
                            100
                            - sum(private["shed"].values())
                            - sum(sum(inv.values()) for inv in private["inventories"])
                        )
                    elif op == "WATER":
                        detail["currently_endangered"] = tile.get("consecutive_unwatered", 0) > 0
                    alternatives.append(detail)
                    counts["pass_with_available:" + op] += 1
                if alternatives:
                    events.append(
                        {
                            "day": day,
                            "hour": hour,
                            "worker": worker,
                            "position": [x, y],
                            "inventory": private["inventories"][worker],
                            "matched_target": matched.get(worker),
                            "alternatives": alternatives,
                        }
                    )
            game._apply_unit_action(farm, private, worker, action, 10, day, 24, 100)
    return {
        "replay": path.as_posix(),
        "replay_sha256": hashlib.sha256(raw).hexdigest(),
        "counts": counts,
        "available_work_events": events,
        "route_compression": route_metrics(replay),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--replays", type=Path, default=Path("reports/replays/phase4-losses"))
    parser.add_argument(
        "--output", type=Path, default=Path("reports/results/phase4-workload.json.gz")
    )
    args = parser.parse_args()
    result = {
        "complete": True,
        "scope": "selected known-loss one-action feasibility, not accumulated cash gains",
        "source_sha256": BASE,
        "interpreter_sha256": hashlib.sha256(Path(game.__file__).read_bytes()).hexdigest(),
        "replays": [analyse(next(args.replays.glob(f"*-{seed}-0.json"))) for seed in (3029, 3063)],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(gzip.compress((json.dumps(result, indent=2) + "\n").encode(), mtime=0))
    print(json.dumps([row["counts"] for row in result["replays"]], indent=2))


if __name__ == "__main__":
    main()
