"""Controlled transport interventions on the immutable v7 policy."""

import argparse
import hashlib
import json
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

from benchmark import episode, provenance, snapshot

INCUMBENT = Path("submissions/20260909-v7/main.py")
DIGEST = "750f123073865347efd3b9c4b72022ff9923f4130c929ac76c1b0742374b09ee"


def replace(source, old, new):
    assert source.count(old) == 1, old
    return source.replace(old, new, 1)


def candidate(name):
    content = INCUMBENT.read_bytes()
    assert hashlib.sha256(content).hexdigest() == DIGEST
    source = content.decode()
    if name in ("nightly", "combined"):
        source = replace(
            source,
            'load >= p["return_load"]',
            '(load >= p["return_load"] and (farm["money"] < 3000 or sum(stock.values()) >= 75 or day == 29))',
        )
    if name == "deadline":
        source = replace(
            source,
            "                c = columns[target]",
            "                if hour + travel > 24 and (required_item or op in ('WATER', 'CARE')):\n"
            "                    continue\n"
            "                c = columns[target]",
        )
    if name in ("delivery_rows", "combined"):
        source = replace(
            source,
            '    if p["matching"]:\n        destinations',
            """    returning = set()
    for i, pos in enumerate(positions):
        inv = inventories[i]
        load = sum(n for item, n in inv.items() if item in BASE
                   and not (item == "WHEAT" and feed_need > 0)
                   and not (item == "FERTILIZER" and fert_tasks > 0))
        home_dist = min(distance(pos, s) for s in shed_tiles)
        end_return = day == 29 and load and hour + home_dist >= 21
        should_return = (pos in shed_tiles and load >= 3) or load >= p["return_load"] or end_return
        if load and should_return and sum(inv.values()) <= shed_room:
            returning.add(i)
    if p["matching"]:
        destinations""",
        )
        source = replace(
            source,
            "        for i, pos in enumerate(positions):\n            home =",
            "        for i, pos in enumerate(positions):\n            if i in returning:\n                continue\n            home =",
        )
        if name == "combined":
            source = replace(
                source,
                'or load >= p["return_load"] or end_return',
                'or (load >= p["return_load"] and (farm["money"] < 3000 or sum(stock.values()) >= 75 or day == 29)) or end_return',
            )
    assert name in ("control", "nightly", "delivery_rows", "combined", "deadline")
    return source


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--names",
        nargs="+",
        default=["control", "nightly", "delivery_rows", "combined", "deadline"],
    )
    parser.add_argument("--seeds", nargs="+", type=int, default=[17, 103])
    parser.add_argument(
        "--opponents",
        nargs="+",
        default=["data/raw/reference-lonespear/main.py", "data/raw/reference-gzm/main.py"],
    )
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--output", type=Path, default=Path("data/raw/phase2-logistics.json"))
    args = parser.parse_args()
    manifest = {
        **provenance([str(INCUMBENT), *args.opponents]),
        "hypothesis": "Transport timing and assignment feasibility",
        "candidates": {},
        "episodes": [],
    }
    tasks = []
    for name in args.names:
        content = candidate(name).encode()
        digest = hashlib.sha256(content).hexdigest()
        path = Path("data/interim/phase2-logistics") / name / digest / "main.py"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
        manifest["candidates"][str(path)] = {
            "name": name,
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
