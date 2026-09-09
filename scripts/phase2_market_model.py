"""Observable-inventory market forecasts and input-reserve counterfactuals.

The forecast is an uncertain servicing scenario, not a replacement game simulator.
"""

from __future__ import annotations

import argparse
import hashlib
import inspect
import json
import math
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

from benchmark import episode, provenance, snapshot
from phase2_logistics import INCUMBENT, replace
from phase2_production import build as production

PRICE_PARAMETERS = {
    "WHEAT": (25, 400, "sqrt", 0.8, "log", 0.2),
    "CARROT": (35, 450, "hinge", 1.0, "sqrt", 0.7),
    "TOMATO": (60, 200, "hinge", 0.4, "sqrt", 0.6),
    "STRAWBERRY": (120, 100, "sqrt", 0.7, "linear", 1.6),
    "MELON": (250, 300, "log", 0.2, "sq", 3.6),
    "EGG": (50, 332, "hinge", 0.4, "log", 0.2),
    "MILK": (160, 122, "sqrt", 0.6, "linear", 1.6),
    "WOOL": (200, 105, "log", 0.2, "sq", 3.2),
    "FERTILIZER": (100, 200, "linear", 0.4, "linear", 0.4),
}


def default_price_parameters():
    return {
        item: dict(
            zip(
                ("base", "T", "below_func", "below_target", "above_func", "above_target"),
                values,
                strict=True,
            ),
            I0=10000,
        )
        for item, values in PRICE_PARAMETERS.items()
    }


def price_shape(kind, amount, scale):
    amount = max(0.0, amount)
    if kind == "sqrt":
        return math.sqrt(amount)
    if kind == "sq":
        return amount**2
    if kind in ("log", "log10"):
        return math.log1p(amount) if kind == "log" else math.log10(1 + amount)
    if kind == "hinge":
        fraction = amount / scale if scale > 0 else amount
        return fraction + 8 * max(0, fraction - 1) ** 2 if scale > 0 else fraction
    return amount


def inventory_quote(inventory, spec):
    shortage = inventory < spec["I0"]
    side = "below" if shortage else "above"
    scale = spec["T"]
    amplitude = spec[side + "_target"] * spec["base"]
    movement = amplitude * price_shape(spec[side + "_func"], abs(inventory - spec["I0"]), scale)
    movement /= price_shape(spec[side + "_func"], scale, scale)
    return max(1, round(spec["base"] + (movement if shortage else -movement)))


def forecast_inventory(obs, crop_specs, animal_specs, shops):
    day = obs["day"]
    market = obs["market"]
    parameters = market.get("params") or default_price_parameters()
    inventory = dict(market["inventory"])
    arrivals = [{item: 0.0 for item in inventory} for _ in range(30)]
    animals = 0
    for farm in obs["farms"]:
        for row in farm["tiles"]:
            for tile in row:
                if not isinstance(tile, dict):
                    continue
                if "animal" in tile:
                    animals += 1
                    _, first, interval, cap, item, _ = animal_specs[tile["animal"]]
                    if day < 29:
                        arrivals[day + 1][item] += tile["yield_units"]
                    for future in range(day + 1, 30):
                        age = future - tile["placed_day"]
                        if age >= first and (age - first) % interval == 0:
                            # Imperfect future care/collection is a scenario assumption.
                            arrivals[future][item] += min(cap, 1 + 0.8 * interval)
                elif tile.get("kind") == "PLANT":
                    item = tile["crop"]
                    _, first, last, interval, cap = crop_specs[item]
                    age = day - tile["planted_day"]
                    if interval:
                        if day < 29:
                            arrivals[day + 1][item] += tile["yield_units"]
                        for event in range(first, first + cap * interval, interval):
                            future = tile["planted_day"] + event
                            if day < future < 30:
                                arrivals[future][item] += 1.5
                    else:
                        target = max(day + 1, tile["planted_day"] + max(first, last - 1))
                        if target < 30:
                            watering_days = max(0, target - day)
                            arrivals[target][item] += min(cap, tile["yield_units"] + watering_days)
    traces = {item: [] for item in inventory}
    initial_shops = obs["town"]["unlocked_shops"]
    for future in range(day + 1, 30):
        demand = {item: (0.0 if item == "FERTILIZER" else 1.0) for item in inventory}
        for shop in initial_shops:
            products = shops[shop]
            for item in products:
                demand[item] += 12 if len(products) == 1 else 6
        extra = min(8 - len(initial_shops), future // 3 - day // 3)
        for products in shops.values():
            for item in products:
                demand[item] += max(0, extra) * (12 if len(products) == 1 else 6) / len(shops)
        demand["WHEAT"] += animals
        arrivals[future]["FERTILIZER"] += animals * 0.5
        for item in inventory:
            inventory[item] += arrivals[future][item] - demand[item]
            traces[item].append(inventory_quote(inventory[item], parameters[item]))
    first_sale = {item: spec[1] for item, spec in crop_specs.items()}
    first_sale.update({spec[4]: spec[1] for spec in animal_specs.values()})
    first_sale["FERTILIZER"] = 1
    forecasts = {}
    for item, values in traces.items():
        if not values:
            forecasts[item] = market["prices"][item]
            continue
        start = min(len(values) - 1, first_sale[item] - 1)
        window = values[start : start + 7]
        forecasts[item] = 0.5 * market["prices"][item] + 0.5 * sum(window) / len(window)
    return forecasts, traces


def build(name):
    source = INCUMBENT.read_text() if name == "v7_model" else production("exact")
    if "model" in name:
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
    if "reserve" in name:
        source = replace(source, "min(10, len(plants) // 2)", "min(20, max(12, len(plants) // 2))")
    return source


def verify():
    from kaggle_environments import make
    from kaggle_environments.envs.kaggriculture import kaggriculture as game

    assert default_price_parameters() == game.MARKET_PARAMS
    compared = 0
    for item, parameters in game.MARKET_PARAMS.items():
        for inventory in range(8000, 12001, 7):
            assert inventory_quote(inventory, parameters) == game.market_price(item, inventory)
            compared += 1
    import importlib.util

    spec = importlib.util.spec_from_file_location("incumbent_probe", INCUMBENT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    env = make("kaggriculture", configuration={"seed": 17, "weedSpawnChance": 0})
    env.reset(2)
    _, predicted = forecast_inventory(
        env.state[0].observation, module.CROPS, module.ANIMALS, module.SHOPS
    )
    checks = 0
    for step in range(48):
        env.step([{}, {}])
        if step in (23, 47):
            offset = (step + 1) // 24 - 1
            for item, trace in predicted.items():
                assert trace[offset] == env.state[0].observation.market.prices[item]
                checks += 1
    print(
        json.dumps(
            {
                "official_curve_comparisons": compared,
                "empty_farm_day_price_comparisons": checks,
                "mismatches": 0,
            }
        )
    )


def diagnose_replays():
    """Offline forecast calibration; future observations are labels only."""
    import importlib.util

    spec = importlib.util.spec_from_file_location("incumbent_probe", INCUMBENT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    records = []
    for path in sorted(Path("data/raw/phase2-frontier-replays").glob("*.json")):
        replay = json.loads(path.read_text())
        observations = {
            turn[0]["observation"]["day"]: turn[0]["observation"]
            for turn in replay["steps"]
            if turn[0]["observation"].get("hour") == 0
        }
        for day in (0, 5, 10, 15, 20):
            obs = observations[day]
            _, trace = forecast_inventory(obs, module.CROPS, module.ANIMALS, module.SHOPS)
            for item, values in trace.items():
                current = obs["market"]["prices"][item]
                actual = observations[day + 5]["market"]["prices"][item]
                forecast = values[4]
                records.append(
                    dict(
                        replay=str(path),
                        day=day,
                        item=item,
                        actual=actual,
                        current=current,
                        model=forecast,
                        blend=(current + forecast) / 2,
                    )
                )
    summary = {}
    for item in PRICE_PARAMETERS:
        subset = [r for r in records if r["item"] == item]
        summary[item] = {
            "checkpoints": len(subset),
            **{
                name + "_mae": sum(abs(r[name] - r["actual"]) for r in subset) / len(subset)
                for name in ("current", "model", "blend")
            },
        }
    target = Path("data/interim/phase2-economics/market-calibration.json")
    target.write_text(
        json.dumps(
            {
                "scope": "offline five-day price forecast diagnostic; current and future observations from known development replays; future labels never used by policy",
                "summary": summary,
                "records": records,
            },
            indent=2,
        )
    )
    print(json.dumps(summary, indent=2))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--verify", action="store_true")
    parser.add_argument("--diagnose-replays", action="store_true")
    parser.add_argument(
        "--names",
        nargs="+",
        default=["v7_model", "exact_model", "exact_reserve", "exact_model_reserve"],
    )
    parser.add_argument("--workers", type=int, default=2)
    parser.add_argument(
        "--output", type=Path, default=Path("data/interim/phase2-economics/market-results.json")
    )
    args = parser.parse_args()
    if args.verify:
        verify()
        return
    if args.diagnose_replays:
        diagnose_replays()
        return
    opponents = ["data/raw/reference-seyam/main.py", "data/raw/reference-cok/main.py"]
    manifest = {**provenance([str(INCUMBENT), *opponents]), "candidates": {}, "episodes": []}
    tasks = []
    for name in args.names:
        content = build(name).encode()
        digest = hashlib.sha256(content).hexdigest()
        target = Path("data/interim/phase2-economics/market") / name / digest / "main.py"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(content)
        manifest["candidates"][str(target)] = {
            "name": name,
            "sha256": digest,
            "snapshot": snapshot(target),
        }
        tasks.extend(
            (str(target), opponent, seed, seat, None)
            for opponent in opponents
            for seed in (17, 103)
            for seat in (0, 1)
        )
    with ProcessPoolExecutor(max_workers=args.workers) as pool:
        for row in pool.map(episode, tasks):
            manifest["episodes"].append(row)
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(json.dumps(manifest, indent=2))
            print(
                manifest["candidates"][row["candidate"]]["name"],
                row["opponent"],
                row["seed"],
                row["seat"],
                row["cash"] - row["opponent_cash"],
                flush=True,
            )


if __name__ == "__main__":
    main()
