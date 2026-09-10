"""Isolated town-timing and dollar-floor supply contract corrections."""

import argparse
import gzip
import hashlib
import inspect
import json
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path


def expected_town_demand(obs, future, shops, items):
    """Expected town consumption until the next observation-day boundary.

    Default verified configuration: 24 turns/day, shops every4 turns, center
    every24 turns, a uniform with-replacement unlock every3 days up to8 instances.
    """
    start = max(obs.get("step", obs["day"] * 24 + obs.get("hour", 0)), (future - 1) * 24)
    stop = future * 24
    shop_ticks = sum(step % 4 == 0 for step in range(start, stop))
    center_ticks = sum(step % 24 == 0 for step in range(start, stop))
    demand = {item: 0.0 if item == "FERTILIZER" else float(center_ticks) for item in items}
    unlocked = obs["town"]["unlocked_shops"]
    for shop in unlocked:
        products = shops[shop]
        for item in products:
            demand[item] += shop_ticks * (2 if len(products) == 1 else 1)
    extra = max(0, min(8 - len(unlocked), (future - 1) // 3 - obs["day"] // 3))
    for products in shops.values():
        for item in products:
            demand[item] += extra * shop_ticks * (2 if len(products) == 1 else 1) / len(shops)
    return demand


def sold_inventory(inventory, amount, spec, quote):
    """Apply the official unit-sale inventory rule, including fractional model mass.

    Integer quantities are interpreter-equivalent. A final fractional forecast
    unit remains an approximation; it is admitted only above the dollar floor.
    """
    while amount > 0 and quote(inventory, spec) > 1:
        unit = min(1.0, amount)
        inventory += unit
        amount -= unit
    return inventory


def build(name):
    digest = "64fe323936dc9494add413eb956b0294658a88efe28572332c94676c68a09325"
    raw = gzip.decompress((Path("reports/sources") / (digest + ".py.gz")).read_bytes())
    assert hashlib.sha256(raw).hexdigest() == digest
    source = raw.decode()
    assert name in ("town_timing", "sale_floor", "both")
    if name in ("town_timing", "both"):
        start = source.index('        demand = {item: (0.0 if item == "FERTILIZER"')
        end = source.index('        demand["WHEAT"] += animals', start)
        source = (
            source[:start]
            + "        demand = expected_town_demand(obs, future, shops, inventory)\n"
            + source[end:]
        )
        source = source.replace(
            "def forecast_inventory(",
            inspect.getsource(expected_town_demand) + "\n\ndef forecast_inventory(",
        )
    if name in ("sale_floor", "both"):
        old = "            inventory[item] += arrivals[future][item] - demand[item]"
        assert source.count(old) == 1
        source = source.replace(
            old,
            "            inventory[item] = sold_inventory(inventory[item], arrivals[future][item], parameters[item], inventory_quote) - demand[item]",
        )
        source = source.replace(
            "def forecast_inventory(",
            inspect.getsource(sold_inventory) + "\n\ndef forecast_inventory(",
        )
    compile(source, name, "exec")
    return source


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--screen", action="store_true")
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--output", type=Path, default=Path("data/raw/phase4-forecast.json"))
    args = parser.parse_args()
    identities = {
        "sale_floor": "000e646a6b8d8a1d2061ea6b8e7c1d3494c4853b217610ade73759abd6ed80c9",
        "both": "1e43a5d7673adff3d44790da79b06323be0fd95be89c1222407e37b25eeb3bf2",
    }
    for name, digest in identities.items():
        assert hashlib.sha256(build(name).encode()).hexdigest() == digest
    if not args.screen:
        print(json.dumps(identities, indent=2))
        return
    assert (
        json.loads(Path("data/raw/phase4-production-interaction.json").read_bytes()).get("complete")
        is True
    ), "Wait for production interaction workers to finish"
    assert 1 <= args.workers <= 4
    assert not args.output.exists(), "Do not overwrite an existing experiment"
    from benchmark import episode, provenance, snapshot

    opponents = [f"data/raw/reference-{name}/main.py" for name in ("seyam", "cok")]
    manifest = {
        **provenance([*opponents, __file__]),
        "base_sha256": "64fe323936dc9494add413eb956b0294658a88efe28572332c94676c68a09325",
        "scope": "32 authorized known-data games: floor correction and timing atop floor",
        "budget_games": 32,
        "seeds": [3000, 3017, 3042, 3063],
        "candidates": {},
        "episodes": [],
        "complete": False,
    }
    tasks = []
    for name, digest in identities.items():
        path = Path("data/interim/phase4-forecast") / name / digest / "main.py"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(build(name).encode())
        manifest["candidates"][str(path)] = {
            "name": name,
            "sha256": digest,
            "snapshot": snapshot(path),
        }
        tasks.extend(
            (str(path), opponent, seed, seat, None)
            for opponent in opponents
            for seed in manifest["seeds"]
            for seat in (0, 1)
        )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    with ProcessPoolExecutor(max_workers=args.workers) as pool:
        for row in pool.map(episode, tasks):
            manifest["episodes"].append(row)
            args.output.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
            print(
                manifest["candidates"][row["candidate"]]["name"],
                row["opponent"],
                row["seed"],
                row["seat"],
                row["cash"] - row["opponent_cash"],
                flush=True,
            )
    assert len(manifest["episodes"]) == len(tasks) == 32
    assert (
        len({(r["candidate"], r["opponent"], r["seed"], r["seat"]) for r in manifest["episodes"]})
        == 32
    )
    for path, metadata in manifest["candidates"].items():
        assert hashlib.sha256(Path(path).read_bytes()).hexdigest() == metadata["sha256"]
    manifest["complete"] = True
    args.output.write_text(json.dumps(manifest, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
