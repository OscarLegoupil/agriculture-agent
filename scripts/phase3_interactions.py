"""Test interactions between demand-led herds and corrected physical execution."""

import argparse
import hashlib
import json
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

from benchmark import episode, provenance, snapshot
from phase2_logistics import replace
from phase3_harvest import build as harvest
from phase3_mix import build as herd

PROFILES = {
    "mixed_growth": (14, 10, False),
    "mixed_service": (14, 10, True),
    "mixed_growth12": (14, 12, False),
    "mixed_capacity": (18, 12, True),
}


def build(name):
    slots, hands, manure = PROFILES[name]
    source = herd(slots, harvest())
    source = replace(source, "PARAMS.update(hands=10)", f"PARAMS.update(hands={hands})")
    if manure:
        source = replace(
            source,
            '"COLLECT_FERTILIZER", 18 if fert_price < 20 else 40',
            '"COLLECT_FERTILIZER", max(1, fert_price)',
        )
    compile(source, name, "exec")
    return source


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--names", nargs="+", choices=PROFILES, default=list(PROFILES))
    parser.add_argument("--seeds", nargs="+", type=int, default=[2000, 2003, 2009, 2013])
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--output", type=Path, default=Path("data/raw/phase3-interactions.json"))
    args = parser.parse_args()
    opponents = [f"data/raw/reference-{name}/main.py" for name in ("seyam", "cok")]
    manifest = {
        **provenance([*opponents, __file__, "scripts/phase3_harvest.py", "scripts/phase3_mix.py"]),
        "hypothesis": "Joint herd allocation, crop growth, manure servicing and capacity have nonadditive effects",
        "candidates": {},
        "episodes": [],
        "complete": False,
    }
    tasks = []
    for name in args.names:
        content = build(name).encode("utf-8")
        digest = hashlib.sha256(content).hexdigest()
        path = Path("data/interim/phase3-interactions") / name / digest / "main.py"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
        manifest["candidates"][str(path)] = {
            "name": name,
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
