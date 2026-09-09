"""Funded inventory holding and bounded market-position experiments."""

from __future__ import annotations

import argparse
import hashlib
import inspect
import json
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

from benchmark import episode, provenance, snapshot
from phase2_logistics import INCUMBENT, replace
from phase2_market_model import (
    PRICE_PARAMETERS,
    default_price_parameters,
    inventory_quote,
    price_shape,
)


def inventory_movement(obs, horizon, crops, animals, shops):
    """Conservative supply scenario; unknown shops add no expected demand."""
    delta = {item: 0.0 for item in obs["market"]["inventory"]}
    day = obs["day"]
    for item in delta:
        if item != "FERTILIZER":
            delta[item] -= horizon
    for shop in obs["town"]["unlocked_shops"]:
        products = shops[shop]
        for item in products:
            delta[item] -= horizon * (12 if len(products) == 1 else 6)
    for farm in obs["farms"]:
        for row in farm["tiles"]:
            for tile in row:
                if not isinstance(tile, dict):
                    continue
                if "animal" in tile:
                    _, first, interval, cap, product, _ = animals[tile["animal"]]
                    delta[product] += tile["yield_units"]
                    for future in range(day + 1, day + horizon + 1):
                        age = future - tile["placed_day"]
                        if age >= first and (age - first) % interval == 0:
                            delta[product] += min(
                                cap, 1 + max(interval, tile.get("pending_care_bonus", 0))
                            )
                elif tile.get("kind") == "PLANT":
                    crop = tile["crop"]
                    _, first, _last, interval, cap = crops[crop]
                    if interval:
                        delta[crop] += tile["yield_units"]
                        for future in range(day + 1, day + horizon + 1):
                            age = future - tile["planted_day"]
                            if (
                                first <= age <= first + (cap - 1) * interval
                                and (age - first) % interval == 0
                            ):
                                delta[crop] += 2
                    elif day + horizon - tile["planted_day"] >= first:
                        delta[crop] += min(cap, tile["yield_units"] + 2 * horizon)
    for inventory in obs["private"]["inventories"]:
        for item, count in inventory.items():
            if item in delta:
                delta[item] += count
    return delta


def market_execution(obs, crops, animals, shops, horizon, positions):
    farm = obs["farms"][obs["player"]]
    shed = obs["private"]["shed"]
    day = obs["day"]
    if day >= 29 or horizon > 29 - day:
        return {}, []
    animal_count = sum(isinstance(t, dict) and "animal" in t for row in farm["tiles"] for t in row)
    daily_labor = 0
    a, b = 1, 1
    for _ in range(max(8, len(farm["hands"]))):
        daily_labor += a
        a, b = b, a + b
    funding = 300 + (horizon + 1) * (daily_labor + animal_count * obs["market"]["prices"]["WHEAT"])
    if farm["money"] < funding:
        return {}, []
    spare = max(
        0, 60 - sum(shed.values()) - sum(sum(i.values()) for i in obs["private"]["inventories"])
    )
    holding_room = min(24, spare)
    delta = inventory_movement(obs, horizon, crops, animals, shops)
    parameters = obs["market"].get("params") or default_price_parameters()
    offers = []
    speculative = []
    for item, inventory in obs["market"]["inventory"].items():
        if item in ("WHEAT", "FERTILIZER"):
            continue
        quantity = shed.get(item, 0)
        # Demand must exceed a fully serviced observable production scenario.
        if delta[item] >= 0:
            continue
        spec = parameters[item]
        now = [0]
        later = [0]
        for unit in range(quantity):
            now.append(now[-1] + inventory_quote(inventory + unit, spec))
            later.append(later[-1] + inventory_quote(inventory + delta[item] + unit, spec))
        best = None
        for held in range(1, min(quantity, holding_room) + 1):
            sold = quantity - held
            current_value = now[-1] - now[sold]
            future_value = later[-1] - later[sold]
            # Storage occupancy and delayed cash both carry an explicit charge.
            gain = future_value - current_value - held * horizon - current_value * 0.01 * horizon
            if gain > 0 and (best is None or gain > best[0]):
                best = (gain, held)
        if best:
            offers.append((best[0] / best[1], item, best[1], quantity))
        if positions and not quantity and farm["money"] > funding + 1000:
            lot = min(5, holding_room, max(0, int(-delta[item]) // 2))
            cost = sum(inventory_quote(inventory - unit - 1, spec) for unit in range(lot))
            future = sum(
                inventory_quote(inventory + delta[item] - lot + unit, spec) for unit in range(lot)
            )
            gain = future - cost - lot * horizon - cost * 0.01 * horizon
            if lot and gain > 0 and cost < farm["money"] - funding:
                speculative.append((gain / cost, item, lot, cost))
    caps = {}
    for _, item, held, quantity in sorted(offers, reverse=True):
        held = min(held, holding_room)
        if held:
            caps[item] = quantity - held
            holding_room -= held
    buys = []
    if speculative and holding_room:
        _, item, lot, _ = max(speculative)
        buys.append(["BUY_PRODUCT", item, min(lot, holding_room)])
    return caps, buys


def build(name):
    source = INCUMBENT.read_text()
    functions = "\n\n".join(
        inspect.getsource(f)
        for f in (
            default_price_parameters,
            price_shape,
            inventory_quote,
            inventory_movement,
            market_execution,
        )
    )
    functions = f"PRICE_PARAMETERS = {PRICE_PARAMETERS!r}\n\n" + functions
    source = replace(source, "def agent(", functions + "\n\ndef agent(")
    horizon = 1 if name == "hold_day" else 2
    source = replace(
        source,
        "    # Sell before buying.",
        f"    sale_caps, speculative_orders = market_execution(obs, CROPS, ANIMALS, SHOPS, {horizon}, {name == 'position'!r})\n\n    # Sell before buying.",
    )
    source = replace(
        source,
        "quantity = max(0, shed.get(item, 0) - reserve)",
        "quantity = min(max(0, shed.get(item, 0) - reserve), sale_caps.get(item, 100000))",
    )
    source = replace(
        source,
        '"market": market[: cfg.get("maxMarketOrdersPerTurn", 10)]',
        '"market": (market + speculative_orders)[: cfg.get("maxMarketOrdersPerTurn", 10)]',
    )
    return source


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--names", nargs="+", default=["hold_day", "hold_two_days", "position"])
    parser.add_argument("--workers", type=int, default=2)
    args = parser.parse_args()
    opponents = ["data/raw/reference-seyam/main.py", "data/raw/reference-cok/main.py"]
    manifest = {**provenance([str(INCUMBENT), *opponents]), "candidates": {}, "episodes": []}
    tasks = []
    for name in args.names:
        content = build(name).encode()
        digest = hashlib.sha256(content).hexdigest()
        target = Path("data/interim/phase2-economics/execution") / name / digest / "main.py"
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
    output = Path("data/interim/phase2-economics/execution-results.json")
    with ProcessPoolExecutor(max_workers=args.workers) as pool:
        for row in pool.map(episode, tasks):
            manifest["episodes"].append(row)
            output.write_text(json.dumps(manifest, indent=2))
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
