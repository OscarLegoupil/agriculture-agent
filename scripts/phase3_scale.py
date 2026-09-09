"""Test the marginal crop space, land and labor funded by the new opening."""

import argparse
import hashlib
import json
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

from benchmark import episode, provenance, snapshot
from phase2_logistics import replace
from phase3_startup import build as opening

SCALES = {
    "fill_three": (65, 3, 12),
    "four_quadrants": (85, 4, 12),
    "four_with_labor": (85, 4, 13),
}


def build(name):
    crops, quadrants, hands = SCALES[name]
    source = replace(
        opening("startup_fert_reserve"),
        "PARAMS.update(crop_tiles=50, quadrants=3, hands=12)",
        f"PARAMS.update(crop_tiles={crops}, quadrants={quadrants}, hands=12)",
    )
    return replace(
        source,
        "PARAMS.update(cows=10, sheep=4, geese=0, hands=12)",
        f"PARAMS.update(cows=10, sheep=4, geese=0, hands={hands})",
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--names", nargs="+", choices=SCALES, default=list(SCALES))
    parser.add_argument("--seeds", nargs="+", type=int, default=[0, 2001])
    parser.add_argument("--workers", type=int, default=3)
    parser.add_argument("--output", type=Path, default=Path("data/raw/phase3-scale.json"))
    args = parser.parse_args()
    opponents = [f"data/raw/reference-{name}/main.py" for name in ("seyam", "cok")]
    manifest = {
        **provenance([*opponents, __file__, "scripts/phase3_startup.py"]),
        "hypothesis": "A crop-financed opening can repay additional serviced recurring cohorts",
        "candidates": {},
        "episodes": [],
        "complete": False,
    }
    tasks = []
    for name in args.names:
        content = build(name).encode("utf-8")
        digest = hashlib.sha256(content).hexdigest()
        path = Path("data/interim/phase3-scale") / name / digest / "main.py"
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
