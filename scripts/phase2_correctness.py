"""Isolate planting admission and input-accounting repairs on the incumbent."""

import argparse
import hashlib
import inspect
import json
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

from benchmark import episode, provenance, snapshot
from phase2_logistics import INCUMBENT, candidate, replace


def build(name):
    source = candidate("control")
    if name == "control":
        return source
    source = replace(
        source,
        'if tile is None:\n                task(x, y, "PLANT", 42, arg=crop)',
        'if tile is None:\n                if hour < 23:\n                    task(x, y, "PLANT", 42, arg=crop)',
    )
    if name != "admission":
        source = replace(source, "min(10, len(plants) // 2)", "min(12, len(plants) // 2)")
        source = replace(
            source,
            'min(12, max(0, fert_tasks - stock["FERTILIZER"]))',
            'max(0, min(12, fert_tasks) - stock["FERTILIZER"])',
        )
    if name.startswith("liquidity"):
        source = replace(
            source,
            'if item == "FERTILIZER" and p["fertilize"] and day < 29:',
            'if item == "FERTILIZER" and p["fertilize"] and day < 29 and cash >= 1000:',
        )
        source = replace(
            source,
            '    if day < 29 and buy_feed and cash > buy_feed * (prices["WHEAT"] + 1):',
            '    buy_feed = min(buy_feed, max(0, int((cash - 20) // (prices["WHEAT"] + 1))))\n    if day < 29 and buy_feed and cash > buy_feed * (prices["WHEAT"] + 1):',
        )
    if "model" in name:
        from phase2_market_model import (
            PRICE_PARAMETERS,
            default_price_parameters,
            forecast_inventory,
            inventory_quote,
            price_shape,
        )

        functions = "\n\n".join(
            inspect.getsource(f)
            for f in (default_price_parameters, price_shape, inventory_quote, forecast_inventory)
        )
        functions = f"PRICE_PARAMETERS = {PRICE_PARAMETERS!r}\n\n" + functions
        source = replace(source, "def agent(", functions + "\n\ndef agent(")
        source = replace(
            source,
            "    # Investment is bounded",
            "    projected, _ = forecast_inventory(obs, CROPS, ANIMALS, SHOPS)\n    forecast.update(projected)\n\n    # Investment is bounded",
        )
    if "expand" in name:
        source = replace(
            source,
            "def agent(",
            "PARAMS.update(crop_tiles=50, quadrants=3, hands=12)\n\n\ndef agent(",
        )
    assert name in (
        "admission",
        "accounting",
        "liquidity",
        "liquidity_expand",
        "liquidity_model",
        "liquidity_model_expand",
    )
    return source


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--names", nargs="+", default=["admission", "accounting", "liquidity"])
    parser.add_argument("--seeds", nargs="+", type=int, default=[17, 103])
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument(
        "--opponents",
        nargs="+",
        default=[
            f"data/raw/reference-{name}/main.py" for name in ("lonespear", "gzm", "seyam", "cok")
        ],
    )
    parser.add_argument("--output", type=Path, default=Path("data/raw/phase2-correctness.json"))
    args = parser.parse_args()
    opponents = args.opponents
    manifest = {
        **provenance([str(INCUMBENT), *opponents]),
        "hypothesis": "Isolated correctness repairs without production scaling",
        "candidates": {},
        "episodes": [],
    }
    tasks = []
    for name in args.names:
        content = build(name).encode()
        digest = hashlib.sha256(content).hexdigest()
        path = Path("data/interim/phase2-correctness") / name / digest / "main.py"
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


if __name__ == "__main__":
    main()
