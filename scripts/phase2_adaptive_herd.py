"""Adaptive species mix on the corrected, expanded inventory-model challenger."""

import argparse
import hashlib
import json
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

from benchmark import episode, provenance, snapshot
from phase2_logistics import replace


def build(base, total):
    source = base.read_text()
    source = replace(
        source,
        'desired = dict(COW=p["cows"], SHEEP=p["sheep"], GOOSE=p["geese"])',
        "desired = dict(COW=14, SHEEP=14, GOOSE=14)",
    )
    source = replace(
        source,
        'if day <= p["animal_stop"]:',
        f'if day <= p["animal_stop"] and sum(stock[a] for a in ANIMALS) < 2 and len(animals) + sum(stock[a] for a in ANIMALS) < {total}:',
    )
    return source


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--total", type=int, choices=(18, 22), default=18)
    parser.add_argument("--seeds", type=int, nargs="+", default=[17, 103])
    parser.add_argument("--workers", type=int, default=2)
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("data/interim/phase2-economics/adaptive-model18-results.json"),
    )
    args = parser.parse_args()
    base = Path(Path("data/raw/phase2-best-path.txt").read_text().strip())
    opponents = ["data/raw/reference-seyam/main.py", "data/raw/reference-cok/main.py"]
    content = build(base, args.total).encode()
    digest = hashlib.sha256(content).hexdigest()
    target = (
        Path("data/interim/phase2-economics/adaptive-model") / str(args.total) / digest / "main.py"
    )
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(content)
    manifest = {
        **provenance([str(base), *opponents]),
        "base": str(base),
        "candidate": str(target),
        "sha256": digest,
        "snapshot": snapshot(target),
        "total_herd": args.total,
        "species_cap": 14,
        "max_pending": 2,
        "episodes": [],
    }
    tasks = [
        (str(target), opponent, seed, seat, None)
        for opponent in opponents
        for seed in args.seeds
        for seat in (0, 1)
    ]
    with ProcessPoolExecutor(max_workers=args.workers) as pool:
        for row in pool.map(episode, tasks):
            manifest["episodes"].append(row)
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(json.dumps(manifest, indent=2))
            print(
                args.total,
                row["opponent"],
                row["seed"],
                row["seat"],
                row["cash"] - row["opponent_cash"],
                flush=True,
            )


if __name__ == "__main__":
    main()
