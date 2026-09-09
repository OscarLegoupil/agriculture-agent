"""Budgeted production search using complete official-interpreter games."""

import argparse
import json
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

from benchmark import episode, provenance, sha, snapshot


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", default="reports/results/production-screen.json")
    parser.add_argument("--seeds", nargs="+", type=int, default=[0, 17])
    parser.add_argument("--workers", type=int, default=2)
    parser.add_argument("--stage", type=int, default=1)
    parser.add_argument("--opponents", nargs="+", default=["data/raw/reference-lonespear/main.py"])
    args = parser.parse_args()
    source = Path("src/kaggriculture/agent/competitive.py").read_text(encoding="utf-8")
    candidates = {
        "mixed": {},
        "compact": {"quadrants": 1, "crop_tiles": 15},
        "herd": {"crop_tiles": 0, "feed_grown": 0, "hands": 10},
        "crop": {"cows": 0, "sheep": 0, "geese": 0, "crop_tiles": 45, "hands": 11},
        "large": {"quadrants": 3, "crop_tiles": 55, "hands": 13},
        "labor13": {"hands": 13},
        "labor9": {"hands": 9},
        "no_fertilizer": {"fertilize": False},
        "cows": {"cows": 14, "sheep": 0, "geese": 0},
        "sheep": {"cows": 0, "sheep": 14, "geese": 0},
        "diverse": {"cows": 6, "sheep": 4, "geese": 4},
        "purchased_feed": {"feed_grown": 0},
    }
    if args.stage == 2:
        candidates = {
            "control": {},
            "strawberry": {"crop_bias": {"STRAWBERRY": 2, "MELON": 0.5}},
            "strawberry_large": {
                "crop_bias": {"STRAWBERRY": 2, "MELON": 0.5},
                "quadrants": 3,
                "crop_tiles": 50,
                "hands": 13,
            },
            "geese": {"cows": 4, "sheep": 6, "geese": 8},
            "balanced": {"cows": 4, "sheep": 4, "geese": 4},
            "sheep_geese": {"cows": 0, "sheep": 8, "geese": 8},
            "more_sheep": {"cows": 4, "sheep": 10, "geese": 0},
            "wheat": {"crop_bias": {"WHEAT": 3, "MELON": 0.5}},
            "carrot": {"crop_bias": {"CARROT": 3, "MELON": 0.5}},
            "labor12": {"hands": 12},
            "labor14": {"hands": 14, "quadrants": 3, "crop_tiles": 50},
            "deliver5": {"return_load": 5},
        }
    if args.stage == 3:
        candidates = {
            "goose_control": {},
            "goose_delivery": {"return_load": 5},
            "goose_labor12": {"hands": 12},
            "goose_labor13": {"hands": 13},
            "goose_compact": {"crop_tiles": 15, "quadrants": 1},
            "goose_early": {"animal_stop": 12},
            "goose_care": {"feed_priority": 130},
            "goose_growth": {"geese": 12, "sheep": 4, "cows": 2, "hands": 12},
        }
        candidates = {
            name: {"cows": 4, "sheep": 6, "geese": 8, **params}
            for name, params in candidates.items()
        }
    if args.stage == 4:
        candidates = {
            "delivery_control": {},
            "opening2": {"opening_geese": 2},
            "opening4": {"opening_geese": 4},
            "opening6": {"opening_geese": 6},
            "drip2": {"sell_batch": 2},
            "drip5": {"sell_batch": 5},
            "feed60": {"feed_priority": 60},
            "early_drip": {"opening_geese": 4, "sell_batch": 3},
        }
    manifest = {
        **provenance(args.opponents),
        "source_hash": sha("src/kaggriculture/agent/competitive.py"),
        "candidates": {},
        "episodes": [],
    }
    tasks = []
    for name, params in candidates.items():
        path = Path("data/interim/candidates") / name / "main.py"
        path.parent.mkdir(parents=True, exist_ok=True)
        # Insert configuration before the entrypoint, preserving last-callable loading.
        path.write_text(
            source.replace("def agent(", f"PARAMS.update({params!r})\n\n\ndef agent(", 1),
            encoding="utf-8",
        )
        manifest["candidates"][str(path)] = {
            "name": name,
            "params": params,
            "sha256": sha(path),
            "snapshot": snapshot(path),
        }
        for seed in args.seeds:
            for seat in (0, 1):
                for opponent in args.opponents:
                    tasks.append((str(path), opponent, seed, seat, None))
    output = Path(args.output)
    with ProcessPoolExecutor(max_workers=args.workers) as pool:
        for row in pool.map(episode, tasks):
            manifest["episodes"].append(row)
            output.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
            print(
                Path(row["candidate"]).parent.name,
                row["seed"],
                row["seat"],
                row["cash"],
                row["opponent_cash"],
                flush=True,
            )


if __name__ == "__main__":
    main()
