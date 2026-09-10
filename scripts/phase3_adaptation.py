"""Test finite crop ranking after the successful startup cohort."""

import argparse
import hashlib
import inspect
import json
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

from benchmark import episode, provenance, snapshot
from phase2_logistics import replace
from phase2_market_model import forecast_inventory
from phase3_cohort_economics import cohort_calendar, cohort_value
from phase3_startup import build as opening


def build(name):
    assert name in ("rate", "profit")
    source = opening("startup_fert_reserve10")
    inventory = inspect.getsource(forecast_inventory)
    inventory = inventory[: inventory.index("    first_sale =")]
    inventory = inventory.replace("def forecast_inventory(", "def cohort_market_inventory(")
    inventory = (
        inventory.replace(
            "traces[item].append(inventory_quote(inventory[item], parameters[item]))",
            "traces[item].append(inventory[item])",
        )
        + "    return traces\n"
    )
    functions = (
        inventory
        + "\n"
        + inspect.getsource(cohort_calendar)
        + "\n"
        + inspect.getsource(cohort_value)
    )
    source = replace(source, "def agent(", functions + "\n\ndef agent(")
    source = replace(
        source,
        "    planned = Counter(crops)",
        '    planned = Counter(crops)\n    cohort_inventory = cohort_market_inventory(obs, CROPS, ANIMALS, SHOPS) if room and free_cells and day < 28 else {}\n    cohort_prices = obs["market"].get("params") or default_price_parameters()',
    )
    source = replace(
        source,
        """crop_value(
                crop, day, forecast[crop] / (1 + planned[crop] * 0.025), fert_price, use_fert and CROPS[crop][3] > 0
            )""",
        f"""cohort_value(
                crop, CROPS[crop], day, min(distance((x, y), s) for s in shed_tiles),
                fert_price, use_fert and CROPS[crop][3] > 0, cohort_inventory[crop], cohort_prices[crop],
                max(0, planned[crop] - crops[crop]), seeds.get(crop, 0) > 0,
                inventory_quote, {name!r}
            )""",
    )
    source = replace(
        source,
        "        if day < 15:\n            target =",
        '        if day < 3 or (day < 15 and planned["WHEAT"] < 7):\n            target =',
    )
    compile(source, name, "exec")
    return source


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--names", nargs="+", choices=("rate", "profit"), default=["rate", "profit"]
    )
    parser.add_argument("--seeds", nargs="+", type=int, default=[0, 2001])
    parser.add_argument("--workers", type=int, default=3)
    parser.add_argument("--output", type=Path, default=Path("data/raw/phase3-adaptation.json"))
    args = parser.parse_args()
    opponents = [f"data/raw/reference-{name}/main.py" for name in ("seyam", "cok")]
    manifest = {
        **provenance(
            [
                *opponents,
                __file__,
                "scripts/phase3_startup.py",
                "scripts/phase3_cohort_economics.py",
            ]
        ),
        "hypothesis": "Market-aware finite cohorts after startup outperform a fixed strawberry follow-on",
        "candidates": {},
        "episodes": [],
        "complete": False,
    }
    tasks = []
    for name in args.names:
        content = build(name).encode("utf-8")
        digest = hashlib.sha256(content).hexdigest()
        path = Path("data/interim/phase3-adaptation") / name / digest / "main.py"
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
