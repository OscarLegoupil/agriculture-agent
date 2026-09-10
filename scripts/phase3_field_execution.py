"""Diagnose recorded field matches through official action transitions; no new games."""

import argparse
import hashlib
import json
from collections import Counter
from copy import deepcopy
from pathlib import Path

from kaggle_environments.envs.kaggriculture import kaggriculture as game

MOVES = {"NORTH", "SOUTH", "EAST", "WEST"}


def analyse(path):
    content = path.read_bytes()
    replay = json.loads(content)
    totals = [Counter(), Counter()]
    harvest = [Counter(), Counter()]
    cohorts = [{}, {}]
    crops = [{}, {}]
    daily = [[Counter() for _ in range(30)] for _ in range(2)]
    harvest_events = [[], []]
    previous = [{}, {}]
    for before, after in zip(replay["steps"], replay["steps"][1:], strict=False):
        obs = before[0]["observation"]
        day, hour = obs["day"], obs["hour"]
        for seat in (0, 1):
            farm = deepcopy(obs["farms"][seat])
            private = deepcopy(before[seat]["observation"]["private"])
            units = [farm["farmer"], *farm["hands"]]
            record = daily[seat][day]
            if hour == 0:
                previous[seat].clear()
                record["cash_start"] = farm["money"]
                record["quadrants"] = len(farm["unlocked_quadrants"])
            record["max_workers"] = max(record["max_workers"], len(units))
            for y, row in enumerate(farm["tiles"]):
                for x, tile in enumerate(row):
                    if not isinstance(tile, dict):
                        continue
                    if "animal" in tile:
                        cohorts[seat][x, y, tile["animal"], tile["placed_day"]] = (
                            tile["animal"],
                            tile["placed_day"],
                        )
                    if "crop" in tile:
                        crops[seat][x, y, tile["crop"], tile["planted_day"]] = (
                            tile["crop"],
                            tile["planted_day"],
                        )
            action = after[seat].get("action") or {}
            actions = [action.get("farmer", ["PASS"]), *action.get("hands", [])]
            actions += [["PASS"]] * max(0, len(units) - len(actions))
            demand = Counter(a[1] for a in actions if len(a) > 1 and a[0] == "PLANT")
            blocked = {c for c, n in demand.items() if n > private["seeds"].get(c, 0)}
            for idx, unit in enumerate(units):
                a = actions[idx]
                if len(a) > 1 and a[0] == "PLANT" and a[1] in blocked:
                    a = ["PASS"]
                op = a[0]
                inv = Counter(private["inventories"][idx])
                x, y = unit
                tile = deepcopy(farm["tiles"][y][x])
                state_before = deepcopy((farm, private))
                game._apply_unit_action(
                    farm,
                    private,
                    idx,
                    a,
                    len(farm["tiles"]),
                    day,
                    24,
                    replay["configuration"].get("shedCapacity", 100),
                )
                new_unit = [farm["farmer"], *farm["hands"]][idx]
                productive = (
                    op not in MOVES | {"PASS", "DROP", "PICKUP"}
                    and (op != "PLACE" or (len(a) > 1 and a[1] in game.ANIMALS))
                    and (farm, private) != state_before
                )
                for counter in (totals[seat], record):
                    counter[op] += 1
                    counter["worker_turns"] += 1
                    counter["productive"] += productive
                    if op != "PASS" and (farm, private) == state_before:
                        counter["unchanged:" + op] += 1
                prior = previous[seat].get(idx)
                if op in MOVES and prior and prior[0] in MOVES and list(new_unit) == prior[1]:
                    totals[seat]["immediate_reverse"] += 1
                    record["immediate_reverse"] += 1
                previous[seat][idx] = (op, list(unit))
                if op == "HARVEST" and isinstance(tile, dict) and "crop" in tile:
                    cf_farm, cf_private = deepcopy(state_before)
                    for cf_action in (["WATER"], ["HARVEST"]):
                        game._apply_unit_action(
                            cf_farm,
                            cf_private,
                            idx,
                            cf_action,
                            len(cf_farm["tiles"]),
                            day,
                            24,
                            replay["configuration"].get("shedCapacity", 100),
                        )
                    actual_gain = Counter(private["inventories"][idx]) - inv
                    counterfactual_gain = Counter(cf_private["inventories"][idx]) - inv
                    extra = counterfactual_gain - actual_gain
                    for crop, amount in extra.items():
                        totals[seat]["water_before_harvest_extra:" + crop] += amount
                        record["water_before_harvest_extra:" + crop] += amount
                        totals[seat]["water_before_harvest_cases:" + crop] += 1
                if op == "HARVEST":
                    gained = Counter(private["inventories"][idx]) - inv
                    harvest[seat].update(gained)
                    for product, amount in gained.items():
                        harvest_events[seat].append(
                            {
                                "day": day,
                                "hour": hour,
                                "product": product,
                                "amount": amount,
                                "age": day - tile.get("planted_day", tile.get("placed_day", day)),
                            }
                        )
                        record["yield:" + product] += amount
                if op == "DROP":
                    returned = inv - Counter(private["inventories"][idx])
                    for product in ("WHEAT", "FERTILIZER"):
                        totals[seat]["returned:" + product] += returned[product]
            if hour == 23:
                for row in farm["tiles"]:
                    for tile in row:
                        if not isinstance(tile, dict):
                            continue
                        if "animal" in tile:
                            for key in ("fed_today", "cared_today"):
                                totals[seat]["animal_days_missing:" + key] += not tile[key]
                                record["animal_days_missing:" + key] += not tile[key]
                        if "crop" in tile:
                            record["crop_days_unwatered"] += not tile["watered_today"]
    ideals = []
    for population in cohorts:
        ideal = Counter()
        for animal, placed in population.values():
            f = game._new_farm(10, 3000)
            t = game._new_animal(animal, placed)
            f["tiles"][0][0] = t
            for day in range(placed, 29):
                t["fed_today"] = True
                t["cared_today"] = True
                game._daily_refresh_animals(f, day)
                ideal[game.ANIMALS[animal]["product"]] += t["yield_units"]
                t["yield_units"] = 0
        ideals.append(dict(ideal))
    return {
        "replay": path.name,
        "replay_sha256": hashlib.sha256(content).hexdigest(),
        "final_cash": [f["money"] for f in replay["steps"][-1][0]["observation"]["farms"]],
        "actions": totals,
        "harvested": harvest,
        "ideal_animal_harvest": ideals,
        "animal_cohorts": [dict(Counter(f"{a}:{d}" for a, d in c.values())) for c in cohorts],
        "crop_cohorts": [dict(Counter(f"{a}:{d}" for a, d in c.values())) for c in crops],
        "daily": daily,
        "harvest_events": harvest_events,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--replays", type=Path, default=Path("reports/replays/phase3-opening-field")
    )
    parser.add_argument(
        "--output", type=Path, default=Path("reports/results/phase3-field-execution.json")
    )
    args = parser.parse_args()
    paths = sorted(args.replays.glob("*cok*200[23]-*.json"))
    if len(paths) != 4:
        parser.error(
            "Expected four saved COK replays for seeds 2002/2003 and both seats; restore the recorded replay directory. This command runs no new games."
        )
    result = {
        "scope": "Post-screen diagnosis on known development data; ideal animal service holds recorded placement cohorts fixed and does not model its labor cost.",
        "replays": [analyse(p) for p in paths],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
