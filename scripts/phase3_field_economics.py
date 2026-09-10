"""Decompose saved replay transitions into verified bilateral economic ledgers.

No policy is executed and no new game or random transition is sampled. Unit and
market helpers run on an independent copy of each recorded preceding state.
Every reconstructed cash balance must match the next recorded observation.
"""

import argparse
import hashlib
import json
from collections import Counter
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace


def analyze(path):
    from kaggle_environments.envs.kaggriculture import kaggriculture as game
    from kaggle_environments.utils import structify

    raw = path.read_bytes()
    replay = json.loads(raw)
    result = {
        "path": str(path),
        "sha256": hashlib.sha256(raw).hexdigest(),
        "interpreter_sha256": hashlib.sha256(Path(game.__file__).read_bytes()).hexdigest(),
        "players": [{"ledger": Counter(), "daily": []} for _ in range(2)],
        "verified_cash_transitions": 0,
    }
    daily_ledgers = [Counter(), Counter()]
    cohorts = [Counter(), Counter()]
    harvests = [Counter(), Counter()]
    originals = {name: getattr(game, name) for name in ("_commit_unit", "_do_hire", "_do_buy_land")}
    farm_seats = {}

    def commit(op, item, price, farm, private, *rest):
        success = originals["_commit_unit"](op, item, price, farm, private, *rest)
        if success:
            seat = farm_seats[id(farm)]
            ledger = daily_ledgers[seat]
            ledger[("income:" if op == "SELL" else "expense:") + item] += price
            ledger["units:" + op + ":" + item] += 1
            ledger["cash:" + op + ":" + item] += price
        return success

    def atomic(name):
        def apply(farm, *rest):
            before = farm["money"]
            value = originals[name](farm, *rest)
            daily_ledgers[farm_seats[id(farm)]][
                "expense:" + ("labor" if name == "_do_hire" else "land")
            ] += before - farm["money"]
            return value

        return apply

    game._commit_unit = commit
    game._do_hire = atomic("_do_hire")
    game._do_buy_land = atomic("_do_buy_land")
    cfg = replay["configuration"]
    env = SimpleNamespace(configuration=structify(cfg))
    try:
        for index, recorded in enumerate(replay["steps"][1:], 1):
            previous = replay["steps"][index - 1]
            state = structify(deepcopy(previous))
            for seat in (0, 1):
                state[seat].action = recorded[seat]["action"]
            obs = state[0].observation
            farm_seats = {id(farm): seat for seat, farm in enumerate(obs.farms)}
            for seat in (0, 1):
                farm, private = obs.farms[seat], state[seat].observation.private
                action = state[seat].action or {}
                actions = [action.get("farmer", ["PASS"]), *action.get("hands", [])]
                demands = Counter(a[1] for a in actions if a and a[0] == "PLANT")
                blocked = {crop for crop, n in demands.items() if n > private["seeds"].get(crop, 0)}
                for unit, task in enumerate(actions):
                    if task and task[0] == "PLANT" and task[1] in blocked:
                        task = ["PASS"]
                    before = Counter()
                    for inv in private["inventories"]:
                        before.update(inv)
                    pos = game._farmer_position(farm, unit)
                    old_tile = deepcopy(farm["tiles"][pos[1]][pos[0]]) if pos else None
                    game._apply_unit_action(
                        farm,
                        private,
                        unit,
                        task,
                        cfg["boardSize"],
                        (index - 1) // cfg["turnsPerDay"],
                        cfg["turnsPerDay"],
                        cfg["shedCapacity"],
                    )
                    if task and task[0] == "HARVEST":
                        after = Counter()
                        for inv in private["inventories"]:
                            after.update(inv)
                        harvests[seat].update(after - before)
                    if pos and task and task[0] in ("PLANT", "PLACE"):
                        new_tile = farm["tiles"][pos[1]][pos[0]]
                        if new_tile != old_tile and isinstance(new_tile, dict):
                            item = new_tile.get("crop", new_tile.get("animal"))
                            if item:
                                cohorts[seat][item] += 1
            game._process_market(state, env)
            for seat in (0, 1):
                assert (
                    obs.farms[seat]["money"] == recorded[0]["observation"]["farms"][seat]["money"]
                ), (path, index, seat)
            result["verified_cash_transitions"] += 2
            if index % cfg["turnsPerDay"] == 0 or index == len(replay["steps"]) - 1:
                for seat in (0, 1):
                    observed = recorded[0]["observation"]
                    farm = observed["farms"][seat]
                    composition = Counter(
                        t.get("crop", t.get("animal", t["kind"]))
                        for row in farm["tiles"]
                        for t in row
                        if isinstance(t, dict)
                    )
                    result["players"][seat]["ledger"].update(daily_ledgers[seat])
                    result["players"][seat]["daily"].append(
                        {
                            "step": index,
                            "cash": farm["money"],
                            "composition": composition,
                            "ledger": daily_ledgers[seat],
                            "new_cohorts": cohorts[seat],
                            "harvested_units": harvests[seat],
                            "land": len(farm["unlocked_quadrants"]),
                            "shops": observed["town"],
                            "market": observed["market"],
                        }
                    )
                    daily_ledgers[seat], cohorts[seat], harvests[seat] = (
                        Counter(),
                        Counter(),
                        Counter(),
                    )
    finally:
        for name, original in originals.items():
            setattr(game, name, original)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--replays", type=Path, default=Path("reports/replays/phase3-opening-field")
    )
    parser.add_argument(
        "--output", type=Path, default=Path("data/interim/phase3-field-economics.json")
    )
    args = parser.parse_args()
    results = []
    for path in sorted(args.replays.glob("*.json")):
        results.append(analyze(path))
        print(path.name, results[-1]["verified_cash_transitions"], flush=True)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps({"method": __doc__, "replays": results}, indent=2) + "\n", encoding="utf-8"
    )


if __name__ == "__main__":
    main()
