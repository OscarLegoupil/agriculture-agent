"""Marginal herd investment including own-revenue price cannibalization."""

import argparse
import copy
import hashlib
import inspect
import json
import sys
import time
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

from benchmark import episode, provenance, snapshot
from phase2_adaptive_herd import build as adaptive
from phase2_logistics import replace


def marginal_animal_values(obs, crop_specs, animal_specs, shops, forecaster, budget=0.04):
    """Pure observed-state scenarios; virtual rows are forecast assets only."""
    deadline = time.perf_counter() + budget
    day = obs["day"]
    base = copy.deepcopy(obs)
    own = base["farms"][base["player"]]
    pending = {}
    for inventory in [base["private"]["shed"], *base["private"]["inventories"]]:
        for animal in animal_specs:
            pending[animal] = pending.get(animal, 0) + inventory.get(animal, 0)
    for animal, count in pending.items():
        for _ in range(count):
            own["tiles"].append([dict(animal=animal, placed_day=day + 1, yield_units=0)])
    existing = [
        tile for row in own["tiles"] for tile in row if isinstance(tile, dict) and "animal" in tile
    ]
    _, old_trace = forecaster(base, crop_specs, animal_specs, shops)
    values = {}
    for animal, spec in animal_specs.items():
        if time.perf_counter() >= deadline:
            print("marginal_investment_budget_fallback", file=sys.stderr)
            return {}
        scenario = copy.deepcopy(base)
        scenario["farms"][scenario["player"]]["tiles"].append(
            [dict(animal=animal, placed_day=day + 1, yield_units=0)]
        )
        _, new_trace = forecaster(scenario, crop_specs, animal_specs, shops)
        cost, first, interval, cap, product, _ = spec
        receipts = 0.0
        existing_change = 0.0
        feed = 0.0
        for offset, future in enumerate(range(day + 1, 30)):
            age = future - (day + 1)
            if age >= first and (age - first) % interval == 0:
                receipts += min(cap, 1 + 0.8 * interval) * new_trace[product][offset]
            feed += new_trace["WHEAT"][offset]
            feed += len(existing) * (new_trace["WHEAT"][offset] - old_trace["WHEAT"][offset])
            for tile in existing:
                _, other_first, other_interval, other_cap, other_product, _ = animal_specs[
                    tile["animal"]
                ]
                other_age = future - tile["placed_day"]
                units = tile["yield_units"] if offset == 0 else 0
                if other_age >= other_first and (other_age - other_first) % other_interval == 0:
                    units += min(other_cap, 1 + 0.8 * other_interval)
                existing_change += units * (
                    new_trace[other_product][offset] - old_trace[other_product][offset]
                )
        values[animal] = receipts + existing_change - feed - cost - (29 - day) * 12
    return values


def build(base):
    source = adaptive(base, 18)
    source = replace(source, "import math", "import copy\nimport math")
    source = replace(
        source, "def agent(", inspect.getsource(marginal_animal_values) + "\n\ndef agent("
    )
    source = replace(
        source,
        "    # Investment is bounded",
        '    marginal_values = (marginal_animal_values(obs, CROPS, ANIMALS, SHOPS, forecast_inventory) if day <= p["animal_stop"] and cash > 450 and sum(stock[a] for a in ANIMALS) < 2 else {})\n\n    # Investment is bounded',
    )
    source = replace(
        source,
        "net = revenue - cost - feed_cost - (29 - day) * 12",
        "net = marginal_values.get(animal, revenue - cost - feed_cost - (29 - day) * 12)",
    )
    return source


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workers", type=int, default=2)
    args = parser.parse_args()
    base = Path(Path("data/raw/phase2-best-path.txt").read_text().strip())
    assert (
        hashlib.sha256(base.read_bytes()).hexdigest()
        == "0098d9e4f77e2420cb4a09abd47e49f5160009cd0818ae37a793bc3e419ffc4b"
    )
    content = build(base).encode()
    digest = hashlib.sha256(content).hexdigest()
    target = Path("data/interim/phase2-economics/marginal-herd") / digest / "main.py"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(content)
    opponents = ["data/raw/reference-seyam/main.py", "data/raw/reference-cok/main.py"]
    manifest = {
        **provenance([str(base), *opponents]),
        "base": str(base),
        "candidate": str(target),
        "sha256": digest,
        "snapshot": snapshot(target),
        "hypothesis": "Own existing animal revenue and feed-cost changes under one additional animal; development only, not a validation candidate",
        "episodes": [],
    }
    tasks = [
        (str(target), opponent, seed, seat, None)
        for opponent in opponents
        for seed in (17, 103)
        for seat in (0, 1)
    ]
    output = Path("data/interim/phase2-economics/marginal-herd-results.json")
    with ProcessPoolExecutor(max_workers=args.workers) as pool:
        for row in pool.map(episode, tasks):
            manifest["episodes"].append(row)
            output.write_text(json.dumps(manifest, indent=2))
            print(
                row["opponent"],
                row["seed"],
                row["seat"],
                row["cash"] - row["opponent_cash"],
                flush=True,
            )


if __name__ == "__main__":
    main()
