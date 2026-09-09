"""Measure actual land purchases, capital timing and quadrant use in saved games."""

import argparse
import gzip
import hashlib
import json
from collections import Counter, defaultdict
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
from statistics import mean

from kaggle_environments.envs.kaggriculture.kaggriculture import _hire_cost


def build(mode="land_only"):
    """Build isolated capacity ablations; this function never runs games."""
    digest = "64fe323936dc9494add413eb956b0294658a88efe28572332c94676c68a09325"
    raw = gzip.decompress((Path("reports/sources") / (digest + ".py.gz")).read_bytes())
    assert hashlib.sha256(raw).hexdigest() == digest
    source = raw.decode()
    assert mode in {"land_only", "crop70", "crop70_hands14"}

    def change(old, new):
        nonlocal source
        assert source.count(old) == 1, old
        source = source.replace(old, new)

    change('"quadrants": 3,', '"quadrants": 4,')
    if mode != "land_only":
        change('"crop_tiles": 50,', '"crop_tiles": 70,')
    if mode == "crop70_hands14":
        change('"hands": 12,', '"hands": 14,')
    change(
        "and len(plants) + len(animals) >= len(cells) - 4",
        """and (
            len(plants) + len(animals) >= len(cells) - 4
            or (len(farm["unlocked_quadrants"]) == 2 and day >= 10 and len(plants) + len(animals) >= 35)
            or (len(farm["unlocked_quadrants"]) == 3 and day >= 12 and len(plants) + len(animals) >= 60)
        )""",
    )
    change(
        'if cash > cost + max(300, feed_need * prices["WHEAT"] + 150):',
        """if cash > cost + max(
            2500 if len(farm["unlocked_quadrants"]) >= 2 else 300,
            feed_need * prices["WHEAT"] + 150,
        ):""",
    )
    compile(source, "land_capacity_experiment", "exec")
    return source


def footprint(farm):
    counts = Counter()
    for y, row in enumerate(farm["tiles"]):
        for x, tile in enumerate(row):
            if isinstance(tile, dict) and ("crop" in tile or "animal" in tile):
                quadrant = ("N" if y < 5 else "S") + ("W" if x < 5 else "E")
                counts[quadrant] += 1
    return dict(counts)


def screen(output, workers, field=False):
    from benchmark import episode, provenance, snapshot

    candidates = {}
    for mode in ["land_only"] if field else ["land_only", "crop70", "crop70_hands14"]:
        raw = build(mode).encode()
        digest = hashlib.sha256(raw).hexdigest()
        if field:
            assert digest == "6c3d587de64242b3f6937b7b0aa2b4fc1369e21851a4539c78c82bcd401223af"
        path = Path("data/interim/phase4-land") / mode / digest / "main.py"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(raw)
        candidates[str(path)] = {"mode": mode, "sha256": digest, "snapshot": snapshot(path)}
    opponents = ["data/raw/reference-cok/main.py", "data/raw/reference-seyam/main.py"]
    manifest = {
        **provenance([*candidates, *opponents]),
        "candidates": candidates,
        "complete": False,
        "episodes": [],
        "hypothesis": "Separate additional land from funded crop capacity and labor commissioning",
    }
    tasks = [
        (c, o, seed, seat, "reports/replays/phase4-land" if seed == 3063 and "cok" in o else None)
        for c in candidates
        for o in opponents
        for seed in (range(3000, 3032) if field else [3000, 3017, 3042, 3063])
        for seat in (0, 1)
    ]
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(manifest, indent=2) + "\n")
    with ProcessPoolExecutor(max_workers=workers) as pool:
        for row in pool.map(episode, tasks):
            manifest["episodes"].append(row)
            output.write_text(json.dumps(manifest, indent=2) + "\n")
            print(
                candidates[row["candidate"]]["mode"],
                row["opponent"],
                row["seed"],
                row["seat"],
                row["cash"],
                row["opponent_cash"],
                flush=True,
            )
    manifest["complete"] = True
    output.write_text(json.dumps(manifest, indent=2) + "\n")


def summarize(path):
    data = json.loads(path.read_bytes())
    assert data["complete"], "Wait for the frozen screen to finish"
    baseline = json.loads(
        gzip.decompress(Path("reports/results/phase3-validation-challenger.json.gz").read_bytes())
    )
    lookup = {(r["opponent"], r["seed"], r["seat"]): r for r in baseline["episodes"]}
    groups = defaultdict(list)
    for row in data["episodes"]:
        groups[(data["candidates"][row["candidate"]]["mode"], row["opponent"])].append(row)
    result = []
    for (mode, opponent), rows in groups.items():
        gaps = [r["cash"] - r["opponent_cash"] for r in rows]
        base = [lookup[r["opponent"], r["seed"], r["seat"]] for r in rows]
        entry = {
            "mode": mode,
            "opponent": opponent,
            "games": len(rows),
            "wins": sum(g > 0 for g in gaps),
            "draws": sum(g == 0 for g in gaps),
            "mean_gap": mean(gaps),
            "paired_gap_change": mean(
                g - b["cash"] + b["opponent_cash"] for g, b in zip(gaps, base, strict=True)
            ),
            "land_purchase_counts": dict(
                Counter(r["ledger"].get("land_purchases", 0) for r in rows)
            ),
            "mean_daily_sampled_peak_productive": mean(
                max(d["crops"] + d["animals"] for d in r["daily"]) for r in rows
            ),
            "baseline_mean_daily_sampled_peak_productive": mean(
                max(d["crops"] + d["animals"] for d in r["daily"]) for r in base
            ),
            "mean_labor_expense": mean(r["ledger"].get("expense:labor", 0) for r in rows),
            "mean_day15_composition": {
                crop: mean(
                    next(d for d in r["daily"] if d["step"] == 360)["composition"].get(crop, 0)
                    for r in rows
                )
                for crop in [
                    "WHEAT",
                    "CARROT",
                    "STRAWBERRY",
                    "MELON",
                    "TOMATO",
                    "COW",
                    "SHEEP",
                    "GOOSE",
                ]
            },
            "mean_wheat_expense": mean(r["ledger"].get("expense:WHEAT", 0) for r in rows),
            "mean_successful_moves": mean(
                sum(
                    r["realized_actions"].get("success:" + a, 0)
                    for a in ["NORTH", "SOUTH", "EAST", "WEST"]
                )
                for r in rows
            ),
            "baseline_mean_successful_moves": mean(
                sum(
                    r["realized_actions"].get("success:" + a, 0)
                    for a in ["NORTH", "SOUTH", "EAST", "WEST"]
                )
                for r in base
            ),
            "mean_successful_harvest_actions": mean(
                r["realized_actions"].get("success:HARVEST", 0) for r in rows
            ),
            "losses": {
                k: sum(r["losses"].get(k, 0) for r in rows)
                for k in ["animal_escapes", "terminal_escapes", "water_deaths", "overflow_units"]
            },
            "stderr_turns": sum(r["stderr_turns"] for r in rows),
            "statuses": dict(Counter(str(r["statuses"]) for r in rows)),
            "runtime_max_seconds": max(r["runtime_max_seconds"] for r in rows),
        }
        result.append(entry)
        print(json.dumps(entry))
    summary_name = (
        "phase4-land-field-summary.json"
        if "field" in path.stem
        else "phase4-land-screen-summary.json"
    )
    (Path("reports/results") / summary_name).write_text(json.dumps(result, indent=2) + "\n")
    geometry = []
    for folder, prefix in [("phase4-land", "6c3"), ("phase4-losses", "64fe")]:
        for replay_path in Path("reports/replays", folder).glob(prefix + "*3063-0.json"):
            replay = json.loads(replay_path.read_bytes())
            entry = {"replay": str(replay_path), "purchases": [], "daily": []}
            for before, after in zip(replay["steps"], replay["steps"][1:], strict=False):
                obs = before[0]["observation"]
                old = obs["farms"][0]
                new = after[0]["observation"]["farms"][0]
                if len(new["unlocked_quadrants"]) > len(old["unlocked_quadrants"]):
                    entry["purchases"].append(
                        {
                            "day": obs["day"],
                            "hour": obs["hour"],
                            "quadrant": new["unlocked_quadrants"][-1],
                            "cash_before_turn": old["money"],
                        }
                    )
            for day in [12, 15, 20, 25]:
                farm = replay["steps"][day * 24][0]["observation"]["farms"][0]
                cells = [
                    (x, y)
                    for y, row in enumerate(farm["tiles"])
                    for x, tile in enumerate(row)
                    if isinstance(tile, dict) and ("animal" in tile or "crop" in tile)
                ]
                distances = [
                    min(abs(x - hx) + abs(y - hy) for hx, hy in [(4, 4), (4, 5), (5, 4), (5, 5)])
                    for x, y in cells
                ]
                entry["daily"].append(
                    {
                        "day": day,
                        "productive": len(cells),
                        "SE": sum(x >= 5 and y >= 5 for x, y in cells),
                        "mean_nearest_shed_distance": mean(distances),
                    }
                )
            geometry.append(entry)
    Path("reports/results/phase4-land-geometry.json").write_text(
        json.dumps(geometry, indent=2) + "\n"
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--screen", action="store_true", help="Run the authorized 48-game development screen"
    )
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument(
        "--field", action="store_true", help="Run frozen land-only on 32 known seeds (128 games)"
    )
    parser.add_argument(
        "--summarize", action="store_true", help="Summarize the completed screen without games"
    )
    parser.add_argument("--output", type=Path, default=Path("data/raw/phase4-land.json"))
    args = parser.parse_args()
    if args.summarize:
        summarize(args.output)
        return
    if args.screen or args.field:
        if args.field and args.output == Path("data/raw/phase4-land.json"):
            args.output = Path("data/raw/phase4-land-field.json")
        screen(args.output, min(4, max(1, args.workers)), args.field)
        return
    manifest_path = Path("reports/results/phase3-validation-challenger.json.gz")
    manifest = json.loads(gzip.decompress(manifest_path.read_bytes()))
    rows = []
    paths = sorted(Path("reports/replays/phase3-validation").glob("*.json"))
    paths += sorted(Path("reports/replays/phase4-losses").glob("*.json"))
    for path in paths:
        raw = path.read_bytes()
        replay = json.loads(raw)
        parts = path.stem.split("-")
        candidate_seat = int(parts[-1])
        for seat in (0, 1):
            purchases = []
            peak = Counter()
            daily = []
            labor_cost = 0
            for index, step in enumerate(replay["steps"]):
                obs = step[0]["observation"]
                farm = obs["farms"][seat]
                used = footprint(farm)
                for quad, count in used.items():
                    peak[quad] = max(peak[quad], count)
                if index % 24 == 0:
                    daily.append(
                        {
                            "day": obs["day"],
                            "cash": farm["money"],
                            "footprint": used,
                            "quadrants": len(farm["unlocked_quadrants"]),
                        }
                    )
                if not index:
                    continue
                prev_obs = replay["steps"][index - 1][0]["observation"]
                prev = prev_obs["farms"][seat]
                if obs["day"] == prev_obs["day"]:
                    labor_cost += sum(
                        _hire_cost(i, replay["configuration"].get("farmHandCostMult", 1))
                        for i in range(prev["hires_today"], farm["hires_today"])
                    )
                new = set(farm["unlocked_quadrants"]) - set(prev["unlocked_quadrants"])
                for quad in sorted(new):
                    purchases.append(
                        {
                            "quadrant": quad,
                            "day": prev_obs["day"],
                            "hour": prev_obs["hour"],
                            "cash_before_turn": prev["money"],
                            "cash_after_turn": farm["money"],
                            "footprint_before": footprint(prev),
                        }
                    )
            rows.append(
                {
                    "replay": path.name,
                    "replay_sha256": hashlib.sha256(raw).hexdigest(),
                    "policy": "v8" if seat == candidate_seat else parts[-4],
                    "seed": int(parts[-2]),
                    "seat": seat,
                    "purchases": purchases,
                    "observed_intraday_labor_cost": labor_cost,
                    "final_total_quadrants": len(farm["unlocked_quadrants"]),
                    "peak_productive_by_quadrant": dict(peak),
                    "daily": daily,
                    "final_footprint": footprint(farm),
                    "peak_total_productive": max(
                        sum(footprint(s[0]["observation"]["farms"][seat]).values())
                        for s in replay["steps"]
                    ),
                    "fill_times": {
                        q: next(
                            (
                                {
                                    "day": s[0]["observation"]["day"],
                                    "hour": s[0]["observation"]["hour"],
                                }
                                for s in replay["steps"]
                                if footprint(s[0]["observation"]["farms"][seat]).get(q, 0) >= 20
                            ),
                            None,
                        )
                        for q in ["NE", "SW", "SE"]
                    },
                }
            )
    grouped = defaultdict(list)
    for row in rows:
        grouped[row["policy"]].append(row)
    summaries = {}
    for policy, games in grouped.items():
        summaries[policy] = {
            "games": len(games),
            "purchased_plot_counts": dict(Counter(len(r["purchases"]) for r in games)),
            "mean_peak_productive_by_quadrant": {
                q: mean(r["peak_productive_by_quadrant"].get(q, 0) for r in games)
                for q in ["NW", "NE", "SW", "SE"]
            },
            "purchases": {
                q: [p for r in games for p in r["purchases"] if p["quadrant"] == q]
                for q in ["NE", "SW", "SE"]
            },
        }
    result = {
        "source_manifest": str(manifest_path),
        "source_hashes": manifest["hashes"],
        "candidate_land_purchases_all_512": dict(
            Counter(r["ledger"].get("land_purchases", 0) for r in manifest["episodes"])
        ),
        "summaries": summaries,
        "replays": rows,
    }
    Path("reports/results/phase4-land-diagnosis.json.gz").write_bytes(
        gzip.compress((json.dumps(result, indent=2) + "\n").encode(), mtime=0)
    )
    for policy, summary in summaries.items():
        print(policy, summary["purchased_plot_counts"], summary["mean_peak_productive_by_quadrant"])
        for q, purchases in summary["purchases"].items():
            if purchases:
                print(
                    q,
                    [
                        (p["day"], p["hour"], p["cash_before_turn"], p["footprint_before"])
                        for p in purchases
                    ],
                )


if __name__ == "__main__":
    main()
