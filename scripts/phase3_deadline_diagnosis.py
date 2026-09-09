"""Verify local feed routes at two recorded escape precursors; no match reruns."""

import argparse
import hashlib
import json
from copy import deepcopy
from pathlib import Path

from kaggle_environments.envs.kaggriculture import kaggriculture as game


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--replay",
        type=Path,
        default=Path(
            "reports/replays/phase3-opening-field/febe9c76051a11e9ea7700e2d4701722e98274c51c50874ad03e1088b9398d4b-reference-cok-main-2009-0.json"
        ),
    )
    parser.add_argument(
        "--output", type=Path, default=Path("reports/results/phase3-deadline-diagnosis.json")
    )
    args = parser.parse_args()
    content = args.replay.read_bytes()
    replay = json.loads(content)
    examples = []
    plans = [(16, 14, 6, [(9, 0)]), (19, 14, 10, [(6, 3), (7, 1)])]
    for day, hour, worker, targets in plans:
        obs = replay["steps"][24 * day + hour][0]["observation"]
        farm = deepcopy(obs["farms"][0])
        private = deepcopy(obs["private"])
        opening_inventory = dict(private["inventories"][worker])
        initial_feed = private["shed"].get("WHEAT", 0)
        actions = [["PICKUP", "WHEAT", len(targets)]]
        pos = [farm["farmer"], *farm["hands"]][worker]
        x, y = pos
        for tx, ty in targets:
            while x != tx:
                actions.append(["EAST" if x < tx else "WEST"])
                x += 1 if x < tx else -1
            while y != ty:
                actions.append(["SOUTH" if y < ty else "NORTH"])
                y += 1 if y < ty else -1
            actions.append(["FEED"])
        assert hour + len(actions) <= 24
        for action in actions:
            game._apply_unit_action(farm, private, worker, action, 10, day, 24, 100)
        assert all(farm["tiles"][y][x]["fed_today"] for x, y in targets)
        assert all(
            private["inventories"][worker].get(k, 0) == v for k, v in opening_inventory.items()
        )
        game._daily_refresh_animals(farm, day)
        survivors = [deepcopy(farm["tiles"][y][x]) for x, y in targets]
        assert all("animal" in t for t in survivors)
        examples.append(
            {
                "day": day,
                "first_hour": hour,
                "last_hour": hour + len(actions) - 1,
                "worker": worker,
                "initial_cash": obs["farms"][0]["money"],
                "initial_shed_wheat": initial_feed,
                "inventory_preserved": opening_inventory,
                "targets": targets,
                "actions": actions,
                "after_daily_refresh": survivors,
            }
        )
    result = {
        "scope": "Local official-action feasibility witnesses at recorded observations, holding other actors and market inactive. These demonstrate physically feasible rescues, not whole-policy replay or guaranteed match benefit.",
        "replay": args.replay.name,
        "replay_sha256": hashlib.sha256(content).hexdigest(),
        "examples": examples,
    }
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
