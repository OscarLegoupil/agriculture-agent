"""Test short-cycle opening capital against long-maturity investment lockup."""

import argparse
import hashlib
import json
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

from benchmark import episode, provenance, snapshot
from phase2_logistics import INCUMBENT, replace
from phase2_production import build


def opening(wheat):
    source = build("recurring")
    source = replace(
        source,
        'if item == "FERTILIZER" and p["fertilize"] and day < 29:',
        'if item == "FERTILIZER" and p["fertilize"] and day < 29 and cash >= 1000:',
    )
    source = replace(
        source,
        "    purchase = None",
        "    if day < 5:\n        desired = dict(COW=2, SHEEP=2, GOOSE=0)\n    purchase = None",
    )
    source = replace(
        source,
        "    workload = len(plants) * 1.4 + len(animals) * 4.5",
        "    workload = max(48 if day < 2 else 0, len(plants) * 1.4 + len(animals) * 4.5)",
    )
    source = replace(
        source,
        "        crop = max(values, key=lambda c: values[c])",
        f'        if day < 3 and planned["WHEAT"] < {wheat}:\n            values["WHEAT"] = max(values.values()) + 1\n        crop = max(values, key=lambda c: values[c])',
    )
    source = replace(
        source, "cash > CROPS[crop][0] + 250", "cash > CROPS[crop][0] + (30 if day < 2 else 250)"
    )
    source = replace(
        source,
        '    if day < 29 and buy_feed and cash > buy_feed * (prices["WHEAT"] + 1):',
        '    buy_feed = min(buy_feed, max(0, int((cash - 20) // (prices["WHEAT"] + 1))))\n    if day < 29 and buy_feed and cash > buy_feed * (prices["WHEAT"] + 1):',
    )
    return source


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--wheat", nargs="+", type=int, default=[6, 10, 14])
    parser.add_argument("--seeds", nargs="+", type=int, default=[17, 103])
    parser.add_argument(
        "--opponents",
        nargs="+",
        default=["data/raw/reference-seyam/main.py", "data/raw/reference-cok/main.py"],
    )
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--output", type=Path, default=Path("data/raw/phase2-opening.json"))
    args = parser.parse_args()
    manifest = {
        **provenance([str(INCUMBENT), *args.opponents]),
        "hypothesis": "Short-cycle crops finance a bounded opening herd and recurring expansion",
        "candidates": {},
        "episodes": [],
    }
    tasks = []
    for wheat in args.wheat:
        content = opening(wheat).encode()
        digest = hashlib.sha256(content).hexdigest()
        path = Path("data/interim/phase2-opening") / str(wheat) / digest / "main.py"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
        manifest["candidates"][str(path)] = {
            "name": f"wheat{wheat}",
            "sha256": digest,
            "snapshot": snapshot(path),
        }
        tasks.extend(
            (str(path), opponent, seed, seat, None)
            for opponent in args.opponents
            for seed in args.seeds
            for seat in (0, 1)
        )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with ProcessPoolExecutor(max_workers=args.workers) as pool:
        for row in pool.map(episode, tasks):
            manifest["episodes"].append(row)
            args.output.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
            print(
                manifest["candidates"][row["candidate"]]["name"],
                row["opponent"],
                row["seed"],
                row["seat"],
                row["cash"],
                row["opponent_cash"],
                flush=True,
            )


if __name__ == "__main__":
    main()
