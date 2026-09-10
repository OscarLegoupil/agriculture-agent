"""Screen mixed and goose-led farms with executable moderate crop expansion."""

import argparse
import hashlib
import json
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

from benchmark import episode, provenance, snapshot
from phase2_logistics import INCUMBENT, replace
from phase2_opening import opening


def candidate(name):
    source = opening(10)
    # Use the current-demand valuation instead of imposing a fourfold berry bias.
    source = replace(
        source, '        if 3 <= day <= 12:\n            values["STRAWBERRY"] *= 2\n', ""
    )
    parameters = dict(
        cows=4,
        sheep=6,
        geese=8,
        crop_tiles=40,
        quadrants=3,
        hands=12,
        feed_grown=8,
        crop_bias={"STRAWBERRY": 1.3},
    )
    if name in ("mixed50", "cashbridge50"):
        parameters["crop_tiles"] = 50
    elif name == "goose44":
        parameters.update(cows=2, sheep=4, geese=14, crop_tiles=44)
        source = replace(
            source,
            "desired = dict(COW=2, SHEEP=2, GOOSE=0)",
            "desired = dict(COW=1, SHEEP=1, GOOSE=2)",
        )
    else:
        assert name == "mixed40"
    if name == "cashbridge50":
        source = replace(
            source,
            'if day < 3 and planned["WHEAT"] < 10:',
            'if day < 10 and planned["WHEAT"] < 10:',
        )
    source = replace(source, "def agent(", f"PARAMS.update({parameters!r})\n\n\ndef agent(")
    compile(source, name, "exec")
    return source


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--names", nargs="+", default=["mixed40", "mixed50", "goose44"])
    parser.add_argument("--seeds", nargs="+", type=int, default=[17, 103])
    parser.add_argument(
        "--opponents",
        nargs="+",
        default=["data/raw/reference-seyam/main.py", "data/raw/reference-cok/main.py"],
    )
    parser.add_argument("--workers", type=int, default=3)
    parser.add_argument("--output", type=Path, default=Path("data/raw/phase2-mixed-expansion.json"))
    args = parser.parse_args()
    manifest = {
        **provenance(
            [
                str(INCUMBENT),
                "scripts/phase2_opening.py",
                "scripts/phase2_production.py",
                *args.opponents,
            ]
        ),
        "hypothesis": "A liquid opening and mixed or goose-led herd can support moderate three-quadrant crop expansion",
        "candidates": {},
        "episodes": [],
    }
    tasks = []
    for name in args.names:
        content = candidate(name).encode()
        digest = hashlib.sha256(content).hexdigest()
        path = Path("data/interim/phase2-mixed-expansion") / name / digest / "main.py"
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
            args.output.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
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
