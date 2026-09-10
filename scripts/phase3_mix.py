"""Let marginal animal values allocate a shared herd budget after startup."""

import argparse
import hashlib
import json
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

from benchmark import episode, provenance, snapshot
from phase2_logistics import replace
from phase3_startup import build as opening


def build(slots, source=None):
    assert slots in (14, 18)
    source = opening("startup_fert_reserve10") if source is None else source
    source = replace(
        source,
        '    desired = dict(COW=p["cows"], SHEEP=p["sheep"], GOOSE=p["geese"])',
        f"    desired = dict.fromkeys(ANIMALS, {slots})",
    )
    source = replace(
        source,
        'if day <= p["animal_stop"] and sum(stock[a] for a in ANIMALS) < 2:',
        f'if day <= p["animal_stop"] and sum(stock[a] for a in ANIMALS) < 2 and len(animals) + sum(stock[a] for a in ANIMALS) < {slots}:',
    )
    compile(source, str(slots), "exec")
    return source


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--slots", nargs="+", type=int, default=[14, 18])
    parser.add_argument("--seeds", nargs="+", type=int, default=[2000, 2003, 2009, 2013])
    parser.add_argument("--workers", type=int, default=3)
    parser.add_argument("--output", type=Path, default=Path("data/raw/phase3-mix.json"))
    args = parser.parse_args()
    opponents = [f"data/raw/reference-{name}/main.py" for name in ("seyam", "cok")]
    manifest = {
        **provenance([*opponents, __file__, "scripts/phase3_startup.py"]),
        "hypothesis": "Shared herd slots let the existing value ranking respond to observed demand",
        "candidates": {},
        "episodes": [],
        "complete": False,
    }
    tasks = []
    for slots in args.slots:
        content = build(slots).encode("utf-8")
        digest = hashlib.sha256(content).hexdigest()
        path = Path("data/interim/phase3-mix") / str(slots) / digest / "main.py"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
        manifest["candidates"][str(path)] = {
            "name": f"slots_{slots}",
            "sha256": digest,
            "snapshot": snapshot(path),
        }
        tasks.extend(
            (str(path), opponent, seed, seat, None)
            for opponent in opponents
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
    for path, metadata in manifest["candidates"].items():
        assert hashlib.sha256(Path(path).read_bytes()).hexdigest() == metadata["sha256"]
    manifest["complete"] = True
    args.output.write_text(json.dumps(manifest, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
