"""Joint crop-expansion and delivery interventions, isolated from deployment."""

import argparse
import hashlib
import json
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

from benchmark import episode, provenance, snapshot
from phase2_logistics import INCUMBENT, candidate, replace

EXACT_CROP_VALUE = """def crop_value(
    crop: str, day: int, price: float, fertilizer_price: float, fertilize: bool
) -> float:
    seed, first, last, interval, cap = CROPS[crop]
    remaining = 29 - day
    if remaining < first:
        return -math.inf
    if interval:
        production = list(range(first, min(remaining, first + (cap - 1) * interval) + 1, interval))
        eves = [event - 1 for event in production]
        life = production[-1]
        units = len(production) * (2 if fertilize else 1)
    else:
        start = (last + 1) // 2
        required = math.ceil((cap - 1) / (2 if fertilize else 1))
        life = max(first, min(remaining, last, start + required - 1))
        eves = list(range(start, min(life, start + required - 1) + 1))
        units = min(cap, 1 + len(eves) * (2 if fertilize else 1))
    applications, active_until = 0, -1
    for eve in eves:
        if fertilize and eve > active_until:
            applications += 1
            active_until = eve + 2
    actions = 3 + life / 2 + len(eves) + applications * 2
    net = units * price - seed - applications * fertilizer_price
    return (net - actions * 4) / (life + 1)


"""


def build(name):
    source = candidate("nightly")
    source = replace(
        source,
        'if tile is None:\n                task(x, y, "PLANT", 42, arg=crop)',
        'if tile is None:\n                if hour < 23:\n                    task(x, y, "PLANT", 42, arg=crop)',
    )
    parameters = dict(cows=8, sheep=4, geese=0, quadrants=3, crop_tiles=60, hands=12)
    route_names = ("recurring", "recurring14", "crop_opening", "compact_recurring")
    if name != "intensive":
        start, end = source.index("def crop_value("), source.index("def agent(")
        source = source[:start] + EXACT_CROP_VALUE + source[end:]
    if name in ("berry", "berry13", *route_names):
        parameters.update(crop_bias={"STRAWBERRY": 2}, feed_grown=12)
    if name == "berry13":
        parameters["hands"] = 13
    if name in route_names:
        # Same-day input targets must agree with sales reserves. This bounds
        # purchases by the target stock, rather than replenishing twelve each turn.
        source = replace(source, "min(10, len(plants) // 2)", "min(12, len(plants) // 2)")
        source = replace(
            source,
            'min(12, max(0, fert_tasks - stock["FERTILIZER"]))',
            'max(0, min(12, fert_tasks) - stock["FERTILIZER"])',
        )
        source = replace(
            source,
            "elif load and home_dist:",
            'elif load and home_dist and (farm["money"] < 3000 or sum(stock.values()) >= 75 or day == 29):',
        )
        source = replace(
            source,
            "elif load and sum(inv.values()) <= shed_room:",
            "elif load and home_dist == 0 and sum(inv.values()) <= shed_room:",
        )
        source = replace(
            source,
            "        crop = max(values, key=lambda c: values[c])",
            '        if 3 <= day <= 12:\n            values["STRAWBERRY"] *= 2\n        crop = max(values, key=lambda c: values[c])',
        )
    if name == "recurring14":
        parameters["hands"] = 14
    if name == "crop_opening":
        parameters.update(cows=4, sheep=2)
        source = replace(source, "if 3 <= day <= 12:", "if day <= 12:")
    if name == "compact_recurring":
        parameters.update(quadrants=2, crop_tiles=40, cows=4, sheep=4, hands=11)
    assert name in ("intensive", "exact", "berry", "berry13", *route_names)
    source = replace(source, "def agent(", f"PARAMS.update({parameters!r})\n\n\ndef agent(")
    return source


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--names", nargs="+", default=["intensive", "exact", "berry", "berry13"])
    parser.add_argument("--seeds", nargs="+", type=int, default=[17, 103])
    parser.add_argument(
        "--opponents",
        nargs="+",
        default=["data/raw/reference-seyam/main.py", "data/raw/reference-cok/main.py"],
    )
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--output", type=Path, default=Path("data/raw/phase2-production.json"))
    args = parser.parse_args()
    manifest = {
        **provenance([str(INCUMBENT), *args.opponents]),
        "hypothesis": "Earlier recurring-crop expansion and nightly transport",
        "candidates": {},
        "episodes": [],
    }
    tasks = []
    for name in args.names:
        content = build(name).encode()
        digest = hashlib.sha256(content).hexdigest()
        path = Path("data/interim/phase2-production") / name / digest / "main.py"
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
