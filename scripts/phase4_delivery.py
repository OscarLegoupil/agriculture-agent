"""Test immediate premium sales after executable shed deliveries."""

import argparse
import gzip
import hashlib
import inspect
import json
from collections import Counter
from pathlib import Path

BASE_SHA256 = "64fe323936dc9494add413eb956b0294658a88efe28572332c94676c68a09325"


def immediate_delivery_sales(obs, cfg, actions, orders):
    """Advance newly deposited premiums only across a no-consumption boundary.

    Project worker-order shed transfers before market execution, preserving
    capacity and current buy order positions. Do not count future moves as drops.
    """
    if obs["day"] >= 29:
        return orders
    farm = obs["farms"][obs["player"]]
    private = obs["private"]
    shed = dict(private["shed"])
    deposited = {}
    size = len(farm["tiles"])
    half = size // 2
    access = {(half - 1, half - 1), (half, half - 1), (half - 1, half), (half, half)}
    capacity = cfg.get("shedCapacity", 100)
    positions = [farm["farmer"], *farm["hands"]]
    for worker, (position, action) in enumerate(zip(positions, actions, strict=False)):
        if tuple(position) not in access or not action:
            continue
        inventory = private["inventories"][worker]
        operation = action[0]
        if operation == "PICKUP" and len(action) >= 2:
            item = action[1]
            quantity = max(0, int(action[2])) if len(action) >= 3 else 1
            shed[item] = shed.get(item, 0) - min(quantity, shed.get(item, 0))
        elif operation in ("DROP", "PLACE"):
            if operation == "DROP":
                items = list(inventory.items())
            elif len(action) >= 2:
                item = action[1]
                tile = farm["tiles"][position[1]][position[0]]
                structure = {"GOOSE": "COOP", "COW": "PASTURE", "SHEEP": "PASTURE"}.get(item)
                if (
                    structure
                    and isinstance(tile, dict)
                    and tile.get("kind") == structure
                    and "animal" not in tile
                ):
                    continue
                quantity = max(0, int(action[2])) if len(action) >= 3 else 1
                items = [(item, min(quantity, inventory.get(item, 0)))]
            else:
                continue
            for item, quantity in items:
                amount = min(max(0, quantity), max(0, capacity - sum(shed.values())))
                shed[item] = shed.get(item, 0) + amount
                deposited[item] = deposited.get(item, 0) + amount
    limit = max(1, cfg.get("maxMarketOrdersPerTurn", 10))
    market = [list(order) for order in orders[:limit]]
    step = obs["step"]
    center_tick = step % max(1, cfg.get("townCenterSellInterval", 24)) == 0
    shop_tick = step % max(1, cfg.get("townShopSellInterval", 4)) == 0
    for item, delivered in deposited.items():
        if item not in ("CARROT", "TOMATO", "STRAWBERRY", "MELON", "EGG", "MILK", "WOOL"):
            continue
        # Every premium is consumed by the center. Existing shops and the clock
        # are public; no future draw or opponent private stock is consulted.
        if center_tick or (
            shop_tick and any(item in SHOPS[shop] for shop in obs["town"]["unlocked_shops"])  # noqa: F821
        ):
            continue
        existing = next((order for order in market if order[:2] == ["SELL", item]), None)
        covered = sum(order[2] for order in market if order[:2] == ["SELL", item])
        extra = min(delivered, max(0, shed.get(item, 0) - covered))
        if extra <= 0:
            continue
        if existing is not None:
            existing[2] += extra
        elif len(market) < limit:
            market.append(["SELL", item, extra])
    return market


def build():
    content = gzip.decompress((Path("reports/sources") / f"{BASE_SHA256}.py.gz").read_bytes())
    assert hashlib.sha256(content).hexdigest() == BASE_SHA256
    source = content.decode("utf-8")
    replacements = (
        ("def agent(", inspect.getsource(immediate_delivery_sales) + "\n\ndef agent("),
        (
            '        "market": market[: cfg.get("maxMarketOrdersPerTurn", 10)],',
            '        "market": immediate_delivery_sales(obs, cfg, actions, market)[: cfg.get("maxMarketOrdersPerTurn", 10)],',
        ),
    )
    for original, replacement in replacements:
        assert source.count(original) == 1
        source = source.replace(original, replacement)
    compile(source, "immediate_delivery_sales.py", "exec")
    return source


def diagnose(replay_dir, output):
    """Count legal advancement opportunities on existing seed-3000 trajectories."""
    namespace = {}
    exec(build(), namespace)
    finalize = namespace["immediate_delivery_sales"]
    results = []
    for path in sorted(replay_dir.glob("*-3000-*.json")):
        if not any(f"reference-{opponent}" in path.name for opponent in ("cok", "seyam")):
            continue
        content = path.read_bytes()
        replay = json.loads(content.decode("utf-8"))
        seat = int(path.stem.rsplit("-", 1)[1])
        units, days = Counter(), Counter()
        first = None
        for index in range(1, len(replay["steps"])):
            previous = replay["steps"][index - 1]
            observation = dict(previous[seat]["observation"])
            for field in ("farms", "market", "town", "day", "hour", "step"):
                observation[field] = previous[0]["observation"][field]
            action = replay["steps"][index][seat].get("action") or {}
            old_orders = action.get("market", [])
            new_orders = finalize(
                observation,
                replay["configuration"],
                [action.get("farmer", ["PASS"]), *action.get("hands", [])],
                old_orders,
            )
            difference = Counter()
            for orders, sign in ((new_orders, 1), (old_orders, -1)):
                for order in orders:
                    if order[0] == "SELL":
                        difference[order[1]] += sign * order[2]
            advanced = {item: quantity for item, quantity in difference.items() if quantity > 0}
            if advanced:
                units.update(advanced)
                days[observation["day"]] += 1
                if first is None:
                    first = {
                        "step": index - 1,
                        "advanced": advanced,
                        "cash": observation["farms"][seat]["money"],
                    }
        results.append(
            {
                "replay": path.as_posix(),
                "replay_sha256": hashlib.sha256(content).hexdigest(),
                "eligible_turns": sum(days.values()),
                "advanced_units": dict(units),
                "turns_by_day": dict(days),
                "first": first,
            }
        )
    if not results:
        raise ValueError("No COK/Seyam seed-3000 replays found")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(
            {
                "scope": "Observation-only eligibility on saved baseline actions; advanced units are not extra revenue",
                "base_sha256": BASE_SHA256,
                "results": results,
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--output", type=Path, default=Path("data/raw/phase4-delivery.json"))
    parser.add_argument(
        "--diagnose-replays", type=Path, help="Read saved replays instead of running a screen"
    )
    args = parser.parse_args()
    if args.diagnose_replays:
        diagnose(args.diagnose_replays, args.output)
        return
    from strategy_screen import screen

    screen(
        {"immediate_delivery": build()},
        [f"data/raw/reference-{name}/main.py" for name in ("seyam", "cok")],
        [3000, 3017, 3042, 3063],
        args.output,
        args.workers,
        inputs=[__file__],
    )


if __name__ == "__main__":
    main()
