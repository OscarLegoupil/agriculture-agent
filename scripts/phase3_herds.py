"""Measure herd expansion after the crop-financed opening."""

import argparse
import hashlib
import json
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

from benchmark import episode, provenance, snapshot
from phase2_logistics import replace
from phase3_startup import build as opening

HERDS = {
    "compact": (6, 2, 0),
    "dairy": (10, 2, 0),
    "large_dairy": (14, 2, 0),
    "mixed": (6, 2, 8),
}


def build(name):
    cows, sheep, geese = HERDS[name]
    return replace(
        opening("startup_fert_reserve"),
        "PARAMS.update(cows=10, sheep=4, geese=0, hands=12)",
        f"PARAMS.update(cows={cows}, sheep={sheep}, geese={geese}, hands=12)",
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--names", nargs="+", choices=HERDS, default=list(HERDS))
    parser.add_argument("--seeds", nargs="+", type=int, default=[0, 2001])
    parser.add_argument("--workers", type=int, default=3)
    parser.add_argument("--output", type=Path, default=Path("data/raw/phase3-herds.json"))
    args = parser.parse_args()
    opponents = [f"data/raw/reference-{name}/main.py" for name in ("seyam", "cok")]
    manifest = {
        **provenance([*opponents, __file__, "scripts/phase3_startup.py"]),
        "hypothesis": "Marginal herd size and mix after an identical two-cow/two-sheep opening",
        "candidates": {},
        "episodes": [],
        "complete": False,
    }
    tasks = []
    for name in args.names:
        content = build(name).encode("utf-8")
        digest = hashlib.sha256(content).hexdigest()
        path = Path("data/interim/phase3-herds") / name / digest / "main.py"
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
