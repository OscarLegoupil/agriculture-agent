"""Screen a bounded one-day inventory reserve on the frozen startup policy."""

# Extracted helpers resolve these functions in the packaged policy namespace.
# ruff: noqa: F821

import argparse
import gzip
import hashlib
import inspect
import json
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

from benchmark import episode, provenance, snapshot
from phase2_logistics import replace

BASE_SHA256 = "febe9c76051a11e9ea7700e2d4701722e98274c51c50874ad03e1088b9398d4b"


def market_reserves(obs, cfg, shed, carried, animals, next_inventory):
    """Retain at most twelve units until the next day's unconditional sale.

    Alternating admission/liquidation days bound duration without episode state.
    Quotes use public production forecasts and current own stocks, never a replay.
    """
    day, hour = obs["day"], obs["hour"]
    if day < 20 or day >= 29 or day % 2:
        return {}
    prices = obs["market"]["prices"]
    farm = obs["farms"][obs["player"]]
    hands = len(farm["hands"])
    a, b, labor = 1, 1, 0
    for _ in range(hands):
        labor += a
        a, b = b, a + b
    obligations = 2 * len(animals) * prices["WHEAT"] + 12 * prices["FERTILIZER"] + 2 * labor
    if farm["money"] < 1000 + obligations:
        return {}
    # All carried products may arrive at the daily reset. Forty more slots cover
    # intervening harvests and input purchases; holding never treats carried stock
    # as free capacity.
    total = sum(shed.values()) + sum(carried.values())
    budget = min(12, max(0, cfg.get("shedCapacity", 100) - total - 40))
    parameters = obs["market"].get("params") or default_price_parameters()
    candidates = []
    for item, quantity in shed.items():
        if item in ("WHEAT", "FERTILIZER") or quantity <= 0 or item not in next_inventory:
            continue
        current = obs["market"]["inventory"][item]
        future = current + (next_inventory[item] - current) * (24 - hour) / 24
        # Own goods outside the reserve must still be sold. Four additional units
        # are a supply stress margin for unobserved opponent inventory.
        future += carried.get(item, 0) + quantity + 4
        n = min(quantity, budget)
        now_value = sum(inventory_quote(current + j, parameters[item]) for j in range(n))
        held_value = sum(inventory_quote(future - n + j, parameters[item]) for j in range(n))
        gain = held_value - now_value
        if gain > max(20, now_value * 0.03):
            candidates.append((gain / n, item, n))
    reserves = {}
    for _, item, amount in sorted(candidates, reverse=True):
        amount = min(amount, budget)
        if amount:
            reserves[item] = amount
            budget -= amount
    return reserves


def build():
    content = gzip.decompress((Path("reports/sources") / f"{BASE_SHA256}.py.gz").read_bytes())
    assert hashlib.sha256(content).hexdigest() == BASE_SHA256
    source = content.decode()
    source = replace(
        source,
        "def forecast_inventory(obs, crop_specs, animal_specs, shops):",
        "def forecast_inventory(obs, crop_specs, animal_specs, shops, first_inventory=False):",
    )
    source = replace(
        source,
        "    traces = {item: [] for item in inventory}",
        "    first_stock = None\n    traces = {item: [] for item in inventory}",
    )
    source = replace(
        source,
        "    first_sale = {item: spec[1] for item, spec in crop_specs.items()}",
        "        if first_stock is None:\n            first_stock = dict(inventory)\n"
        "    if first_inventory:\n        return first_stock or inventory\n"
        "    first_sale = {item: spec[1] for item, spec in crop_specs.items()}",
    )
    source = replace(source, "def agent(", inspect.getsource(market_reserves) + "\n\ndef agent(")
    source = replace(
        source,
        "    # Sell before buying.",
        "    hold = market_reserves(obs, cfg, shed, carried, animals,\n"
        "        forecast_inventory(obs, CROPS, ANIMALS, SHOPS, True))\n\n"
        "    # Sell before buying.",
    )
    source = replace(
        source,
        "        quantity = max(0, shed.get(item, 0) - reserve)",
        "        quantity = max(0, shed.get(item, 0) - max(reserve, hold.get(item, 0)))",
    )
    compile(source, "one_day_market.py", "exec")
    return source


def probe():
    from kaggle_environments.envs.kaggriculture import kaggriculture as game

    namespace = {}
    exec(build(), namespace)
    spec = namespace["default_price_parameters"]()
    for item in spec:
        for inventory in range(-40, 81, 10):
            assert namespace["inventory_quote"](inventory, spec[item]) == game.market_price(
                item, inventory, spec
            )
    spec["TOMATO"]["I0"] = 0
    obs = {
        "day": 20,
        "hour": 0,
        "player": 0,
        "farms": [{"money": 10000, "hands": []}],
        "market": {
            "inventory": {"TOMATO": 40},
            "prices": {"WHEAT": 20, "FERTILIZER": 30},
            "params": spec,
        },
    }
    reserve = namespace["market_reserves"]
    assert reserve(obs, {}, {"TOMATO": 10}, {}, [], {"TOMATO": -100}) == {"TOMATO": 10}
    obs["day"] = 21
    assert not reserve(obs, {}, {"TOMATO": 10}, {}, [], {"TOMATO": 0})
    obs["day"] = 29
    assert not reserve(obs, {}, {"TOMATO": 10}, {}, [], {"TOMATO": 0})
    obs["day"] = 20
    assert not reserve(obs, {}, {"TOMATO": 10}, {"WHEAT": 60}, [], {"TOMATO": 0})
    obs["farms"][0]["money"] = 100
    assert not reserve(obs, {}, {"TOMATO": 10}, {}, [], {"TOMATO": 0})
    print("117 official price checks and five reserve feasibility checks passed")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--probe", action="store_true")
    parser.add_argument("--workers", type=int, default=2)
    args = parser.parse_args()
    if args.probe:
        probe()
        return
    content = build().encode()
    digest = hashlib.sha256(content).hexdigest()
    path = Path("data/interim/phase3-market") / digest / "main.py"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
    opponents = [f"data/raw/reference-{name}/main.py" for name in ("seyam", "cok")]
    manifest = {
        **provenance([str(path), *opponents]),
        "base_sha256": BASE_SHA256,
        "candidate_snapshot": snapshot(path),
        "complete": False,
        "episodes": [],
    }
    tasks = [
        (str(path), opponent, seed, seat, None)
        for opponent in opponents
        for seed in (0, 2001)
        for seat in (0, 1)
    ]
    output = Path("data/raw/phase3-market.json")
    with ProcessPoolExecutor(max_workers=args.workers) as pool:
        for row in pool.map(episode, tasks):
            manifest["episodes"].append(row)
            output.write_text(json.dumps(manifest, indent=2))
            print(
                row["opponent"],
                row["seed"],
                row["seat"],
                row["cash"],
                row["opponent_cash"],
                flush=True,
            )
    assert len(manifest["episodes"]) == len(tasks)
    assert hashlib.sha256(path.read_bytes()).hexdigest() == digest
    manifest["complete"] = True
    manifest["completion_validation"] = {
        "expected_scenarios": len(tasks),
        "artifact_sha256": digest,
    }
    output.write_text(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
