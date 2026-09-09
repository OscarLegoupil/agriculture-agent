"""Diagnose known v7 games and run small official-environment counterfactuals."""

from __future__ import annotations

import argparse
import gzip
import json
from collections import Counter
from concurrent.futures import ProcessPoolExecutor
from copy import deepcopy
from pathlib import Path
from statistics import mean

from benchmark import episode, provenance, sha


def exact_refresh_events(replay: dict, seat: int) -> list[dict]:
    """Reapply recorded worker actions and plant transitions with official helpers.

    Market actions cannot alter field plants; these isolated plant transitions
    therefore reproduce the complete episode without guessing intra-turn order.
    In particular a newly planted crop can die before a replay stores its state.
    This is offline diagnosis, never an input to the deployed policy.
    """
    from kaggle_environments.envs.kaggriculture import kaggriculture as game

    cfg = replay["configuration"]
    turns = cfg.get("turnsPerDay", 24)
    events = []
    for step, following in zip(replay["steps"], replay["steps"][1:], strict=False):
        obs = {**step[0]["observation"], **step[seat]["observation"]}
        if (obs["step"] + 1) % turns:
            continue
        farm = deepcopy(obs["farms"][seat])
        private = deepcopy(obs["private"])
        action = following[seat].get("action") or {}
        actions = [action.get("farmer", ["PASS"]), *action.get("hands", [])]
        plants = Counter(a[1] for a in actions if len(a) > 1 and a[0] == "PLANT")
        blocked = {c for c, n in plants.items() if n > private["seeds"].get(c, 0)}
        new_positions = set()
        for idx, act in enumerate(actions):
            if len(act) > 1 and act[0] == "PLANT" and act[1] in blocked:
                act = ["PASS"]
            position = game._farmer_position(farm, idx)
            if position is not None and act and act[0] == "PLANT":
                new_positions.add(tuple(position))
            game._apply_unit_action(
                farm,
                private,
                idx,
                act,
                len(farm["tiles"]),
                obs["day"],
                turns,
                cfg.get("shedCapacity", 100),
            )
        game._decay_plants(farm, obs["step"])
        before = deepcopy(farm["tiles"])
        game._daily_refresh_plants(farm, obs["day"], turns)
        actual = following[seat]["observation"]["farms"][seat]["tiles"]
        for y, row in enumerate(before):
            for x, tile in enumerate(row):
                if not isinstance(tile, dict) or tile.get("kind") != "PLANT":
                    continue
                after = farm["tiles"][y][x]
                if after != actual[y][x]:
                    raise AssertionError(f"Official replay plant mismatch at {obs['step']} {x, y}")
                if after.get("kind") != "WEED":
                    continue
                spec = game.CROPS[tile["crop"]]
                age = obs["day"] - tile["planted_day"]
                exhausted = (
                    spec["ongoing"]
                    and age >= spec["first_yield_day"] + (spec["max_yield"] - 1) * spec["interval"]
                    and not tile["yield_units"]
                )
                cause = (
                    "exhausted_abandonment"
                    if exhausted
                    else "planting_without_water_opportunity"
                    if (x, y) in new_positions
                    else "missed_existing_crop_water"
                )
                events.append(
                    {
                        "day": obs["day"],
                        "position": [x, y],
                        "crop": tile["crop"],
                        "age": age,
                        "yield": tile["yield_units"],
                        "cause": cause,
                    }
                )
    return events


def analyze_replay(path: str, seat: int) -> dict:
    replay = json.loads(Path(path).read_text())
    events = []
    reversals = Counter()
    previous_moves = {}
    opposites = {"NORTH": "SOUTH", "SOUTH": "NORTH", "EAST": "WEST", "WEST": "EAST"}
    for step, following in zip(replay["steps"], replay["steps"][1:], strict=False):
        obs = step[seat]["observation"]
        nxt = following[seat]["observation"]
        before, after = obs["farms"][seat], nxt["farms"][seat]
        action = following[seat].get("action") or {}
        for worker, act in enumerate([action.get("farmer", ["PASS"]), *action.get("hands", [])]):
            op = act[0] if act else "PASS"
            if opposites.get(op) == previous_moves.get(worker):
                reversals["immediate_move_reversals"] += 1
            previous_moves[worker] = op
        for y, row in enumerate(before["tiles"]):
            for x, tile in enumerate(row):
                new = after["tiles"][y][x]
                if not isinstance(tile, dict) or tile.get("kind") != "PLANT":
                    continue
                if not isinstance(new, dict) or new.get("kind") != "WEED":
                    continue
                age = obs["day"] - tile["planted_day"]
                crop = tile["crop"]
                last_event = {"TOMATO": 11, "STRAWBERRY": 16}.get(crop)
                exhausted = last_event is not None and age >= last_event and not tile["yield_units"]
                at_refresh = nxt["day"] > obs["day"]
                cause = (
                    "exhausted"
                    if exhausted
                    else "missed_water"
                    if at_refresh and not tile["watered_today"] and tile["consecutive_unwatered"]
                    else "decay"
                )
                events.append(
                    {
                        "day": obs["day"],
                        "hour": obs["hour"],
                        "crop": crop,
                        "age": age,
                        "yield": tile["yield_units"],
                        "cause": cause,
                        "position": [x, y],
                        "price": obs["market"]["prices"][crop],
                    }
                )
    exact = exact_refresh_events(replay, seat)
    return {
        "events": events,
        "counts": dict(Counter(e["cause"] for e in events)),
        "exact_eod_events": exact,
        "exact_eod_counts": dict(Counter(e["cause"] for e in exact)),
        **reversals,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--counterfactuals", action="store_true")
    parser.add_argument("--workers", type=int, default=3)
    args = parser.parse_args()
    folder = Path("data/interim/phase2-diagnosis")
    folder.mkdir(parents=True, exist_ok=True)
    historical = json.loads(
        gzip.decompress(Path("reports/results/holdout-v7.json.gz").read_bytes())
    )
    rows = [e for e in historical["episodes"] if "tina" not in e["opponent"]]
    summary = {
        "incumbent_sha256": sha("submissions/20260909-v7/main.py"),
        "known_data": "phase-one holdout, now development data",
        "groups": {},
        "replays": [],
    }
    for label, subset in (
        ("wins", [e for e in rows if e["cash"] > e["opponent_cash"]]),
        ("losses", [e for e in rows if e["cash"] < e["opponent_cash"]]),
    ):
        keys = sorted({k for e in subset for k in e["ledger"]})
        summary["groups"][label] = {
            "games": len(subset),
            "cash": mean(e["cash"] for e in subset),
            "gap": mean(e["cash"] - e["opponent_cash"] for e in subset),
            "ledger": {k: mean(e["ledger"].get(k, 0) for e in subset) for k in keys},
            "actions": {
                k: mean(e["realized_actions"].get(k, 0) for e in subset)
                for k in sorted({k for e in subset for k in e["realized_actions"]})
            },
        }
    selected = [e for e in rows if e["seed"] in (10000, 10017)]
    for row in selected:
        summary["replays"].append(
            {
                "seed": row["seed"],
                "seat": row["seat"],
                "opponent": row["opponent"],
                "gap": row["cash"] - row["opponent_cash"],
                **analyze_replay(row["replay_path"], row["seat"]),
            }
        )
    (folder / "diagnosis.json").write_text(json.dumps(summary, indent=2) + "\n")
    if not args.counterfactuals:
        return
    source = Path("submissions/20260909-v7/main.py").read_text()
    changes = {
        "water_urgency": source.replace("else 115\n", "else 200\n"),
        "larger_feed_pickups": source.replace(
            '3 if required == "WHEAT" else 4', '6 if required == "WHEAT" else 4'
        ),
        "exclude_delivery_workers": source.replace(
            "            home = min(shed_tiles, key=lambda s: distance(pos, s))\n            for target, op",
            '            home = min(shed_tiles, key=lambda s: distance(pos, s))\n            inv = inventories[i]\n            delivery_load = sum(n for item, n in inv.items() if item in BASE and not (item == "WHEAT" and feed_need > 0) and not (item == "FERTILIZER" and fert_tasks > 0))\n            end_delivery = day == 29 and delivery_load and hour + distance(pos, home) >= 21\n            if delivery_load and ((pos in shed_tiles and delivery_load >= 3) or delivery_load >= p["return_load"] or end_delivery) and sum(inv.values()) <= shed_room:\n                continue\n            for target, op',
        ),
    }
    tasks = []
    paths = []
    for label, code in changes.items():
        if code == source:
            raise ValueError(f"No change for {label}")
        path = folder / label / "main.py"
        path.parent.mkdir(exist_ok=True)
        path.write_bytes(code.encode())
        paths.append(str(path))
        tasks.extend((str(path), e["opponent"], e["seed"], e["seat"], None) for e in selected)
    results = {
        **provenance([*paths, *sorted({e["opponent"] for e in selected})]),
        "hypotheses": list(changes),
        "baseline": selected,
        "episodes": [],
    }
    with ProcessPoolExecutor(max_workers=args.workers) as pool:
        for row in pool.map(episode, tasks):
            results["episodes"].append(row)
            (folder / "counterfactuals.json").write_text(json.dumps(results, indent=2) + "\n")
            print(
                Path(row["candidate"]).parent.name,
                row["opponent"],
                row["seed"],
                row["seat"],
                row["cash"] - row["opponent_cash"],
                flush=True,
            )


if __name__ == "__main__":
    main()
