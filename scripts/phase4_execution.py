"""Diagnose completed release validation using recorded official transitions."""

import argparse
import gzip
import json
from collections import Counter
from copy import deepcopy
from pathlib import Path
from statistics import mean

from kaggle_environments.envs.kaggriculture import kaggriculture as game
from phase3_field_execution import analyse


def service_decomposition(replay):
    flags = [{}, {}]
    production_losses = [[], []]
    for step, after in zip(replay["steps"], replay["steps"][1:], strict=False):
        obs = step[0]["observation"]
        if obs["hour"] != 23:
            continue
        day = obs["day"]
        for seat in (0, 1):
            farm = deepcopy(obs["farms"][seat])
            private = deepcopy(step[seat]["observation"]["private"])
            a = after[seat].get("action") or {}
            actions = [a.get("farmer", ["PASS"]), *a.get("hands", [])]
            demand = Counter(x[1] for x in actions if len(x) > 1 and x[0] == "PLANT")
            blocked = {c for c, n in demand.items() if n > private["seeds"].get(c, 0)}
            for idx, action in enumerate(actions):
                if len(action) > 1 and action[0] == "PLANT" and action[1] in blocked:
                    action = ["PASS"]
                game._apply_unit_action(
                    farm,
                    private,
                    idx,
                    action,
                    len(farm["tiles"]),
                    day,
                    24,
                    replay["configuration"].get("shedCapacity", 100),
                )
            for y, row in enumerate(farm["tiles"]):
                for x, t in enumerate(row):
                    if isinstance(t, dict) and "animal" in t:
                        spec = game.ANIMALS[t["animal"]]
                        age = day + 1 - t["placed_day"]
                        if (
                            not t["fed_today"]
                            and age >= spec["first_yield_day"]
                            and (age - spec["first_yield_day"]) % spec["interval"] == 0
                            and t.get("pending_care_bonus", 0)
                        ):
                            outputs = []
                            for fed in (False, True):
                                probe = game._new_farm(10, 3000)
                                probe["tiles"][0][0] = deepcopy(t)
                                probe["tiles"][0][0]["fed_today"] = fed
                                game._daily_refresh_animals(probe, day)
                                outputs.append(probe["tiles"][0][0].get("yield_units", 0))
                            production_losses[seat].append(
                                {
                                    "day": day,
                                    "x": x,
                                    "y": y,
                                    "animal": t["animal"],
                                    "product": spec["product"],
                                    "pending_care_bonus": t["pending_care_bonus"],
                                    "extra_units_if_fed": outputs[1] - outputs[0],
                                }
                            )
                        key = (x, y, t["animal"], t["placed_day"])
                        flags[seat].setdefault(key, {})[day] = (t["fed_today"], t["cared_today"])
    result = []
    for seat in (0, 1):
        modes = {}
        missing = Counter()
        for key, calendar in flags[seat].items():
            for day, (fed, cared) in calendar.items():
                if day <= 26:
                    missing[key[2] + ":fed_without_care"] += fed and not cared
                    missing[key[2] + ":unfed"] += not fed
        for mode in [
            "actual_service_immediate_collection",
            "care_when_actually_fed",
            "ideal_feed_and_care",
        ]:
            products = Counter()
            for key, calendar in flags[seat].items():
                animal, placed = key[2:]
                farm = game._new_farm(10, 3000)
                farm["tiles"][0][0] = game._new_animal(animal, placed)
                for day in range(placed, 29):
                    tile = farm["tiles"][0][0]
                    if "animal" not in tile:
                        break
                    fed, cared = calendar.get(day, (False, False))
                    tile["fed_today"] = True if mode == "ideal_feed_and_care" else fed
                    tile["cared_today"] = (
                        cared
                        if mode == "actual_service_immediate_collection"
                        else tile["fed_today"]
                    )
                    game._daily_refresh_animals(farm, day)
                    tile = farm["tiles"][0][0]
                    if "animal" not in tile:
                        break
                    products[game.ANIMALS[animal]["product"]] += tile["yield_units"]
                    tile["yield_units"] = 0
            modes[mode] = dict(products)
        result.append(
            {
                "modes": modes,
                "nonterminal_missing_service": dict(missing),
                "production_eve_feed_losses": production_losses[seat],
            }
        )
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--manifest",
        type=Path,
        default=Path("reports/results/phase3-validation-challenger.json.gz"),
    )
    parser.add_argument("--replays", type=Path, default=Path("reports/replays/phase3-validation"))
    parser.add_argument(
        "--output", type=Path, default=Path("reports/results/phase4-execution.json.gz")
    )
    args = parser.parse_args()
    manifest = json.loads(gzip.decompress(args.manifest.read_bytes()))
    assert manifest["complete"]
    rows = [r for r in manifest["episodes"] if "cok" in r["opponent"]]
    groups = {}
    for label, rs in [
        ("wins", [r for r in rows if r["cash"] > r["opponent_cash"]]),
        ("losses", [r for r in rows if r["cash"] <= r["opponent_cash"]]),
    ]:
        groups[label] = {
            "games": len(rs),
            "cash": mean(r["cash"] for r in rs),
            "gap": mean(r["cash"] - r["opponent_cash"] for r in rs),
            "losses": sum((Counter(r["losses"]) for r in rs), Counter()),
            "ledger_means": {
                k: mean(r["ledger"].get(k, 0) for r in rs)
                for k in sorted(set().union(*(r["ledger"] for r in rs)))
            },
            "action_means": {
                k: mean(r["realized_actions"].get(k, 0) for r in rs)
                for k in sorted(set().union(*(r["realized_actions"] for r in rs)))
            },
        }
    paths = sorted(args.replays.glob("*cok*300[01]-*.json"))
    assert len(paths) == 4
    paths += sorted(Path("reports/replays/phase4-losses").glob("*cok*.json"))
    assert len(paths) == 8
    result = {
        "scope": "Completed validation is now known development. Four original saved COK matches are wins; four subsequently reproduced known losses supplement diagnosis. The selection is not a random sample. No new games.",
        "groups": groups,
        "replays": [],
    }
    for path in paths:
        entry = analyse(path)
        replay = json.loads(path.read_bytes())
        entry["service_decomposition"] = service_decomposition(replay)
        final = replay["steps"][-1][0]["observation"]
        stranded = []
        for farm in final["farms"]:
            assets = []
            for y, row in enumerate(farm["tiles"]):
                for x, t in enumerate(row):
                    if not isinstance(t, dict) or t.get("yield_units", 0) <= 0:
                        continue
                    crop = t.get("crop")
                    product = crop or {"COW": "MILK", "SHEEP": "WOOL", "GOOSE": "EGG"}.get(
                        t.get("animal")
                    )
                    if product:
                        assets.append(
                            {
                                "x": x,
                                "y": y,
                                "product": product,
                                "units": t["yield_units"],
                                "quote_upper_value": t["yield_units"]
                                * final["market"]["prices"][product],
                            }
                        )
            stranded.append(assets)
        deaths = []
        for before, after in zip(replay["steps"], replay["steps"][1:], strict=False):
            obs = before[0]["observation"]
            for seat in (0, 1):
                for y, row in enumerate(obs["farms"][seat]["tiles"]):
                    for x, tile in enumerate(row):
                        new_tile = after[0]["observation"]["farms"][seat]["tiles"][y][x]
                        if (
                            not isinstance(tile, dict)
                            or "crop" not in tile
                            or not isinstance(new_tile, dict)
                            or new_tile.get("kind") != "WEED"
                        ):
                            continue
                        spec = game.CROPS[tile["crop"]]
                        expired = (
                            tile["max_lifespan_step"] >= 0
                            and obs["step"] >= tile["max_lifespan_step"]
                        )
                        exhausted = (
                            spec["ongoing"]
                            and obs["day"] - tile["planted_day"]
                            >= spec["first_yield_day"] + (spec["max_yield"] - 1) * spec["interval"]
                            and not tile["yield_units"]
                        )
                        deaths.append(
                            {
                                "seat": seat,
                                "day": obs["day"],
                                "hour": obs["hour"],
                                "x": x,
                                "y": y,
                                "crop": tile["crop"],
                                "units_before": tile["yield_units"],
                                "reason": "lifespan"
                                if expired
                                else "exhausted_irrigation_abandonment"
                                if exhausted
                                else "water_deadline",
                            }
                        )
        entry["crop_death_events"] = deaths
        entry["terminal_field_inventory"] = stranded
        result["replays"].append(entry)
        print(path.name, entry["final_cash"], flush=True)
    experiment_service = []
    for prefix, mode in [("1333b40f", "daily_escape_first"), ("401b58a6", "banked_escape_first")]:
        matched = sorted(Path("reports/replays/phase4-care").glob(prefix + "*3063-0.json"))
        for path in matched:
            replay = json.loads(path.read_bytes())
            experiment_service.append(
                {"mode": mode, "replay": path.name, "service": service_decomposition(replay)}
            )
    result["corrected_feed_service_diagnostics"] = experiment_service
    # Retain the established CRLF serialization while compressing deterministically.
    serialized = (
        (json.dumps(result, indent=2, sort_keys=True) + "\n").replace("\n", "\r\n").encode("utf-8")
    )
    args.output.write_bytes(
        gzip.compress(serialized, mtime=0) if args.output.suffix == ".gz" else serialized
    )


if __name__ == "__main__":
    main()
