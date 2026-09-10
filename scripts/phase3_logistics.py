"""Test cash- and capacity-aware delivery on the frozen expanded challenger."""

import argparse
import gzip
import hashlib
import json
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

from benchmark import episode, provenance, snapshot

DIGEST = "0098d9e4f77e2420cb4a09abd47e49f5160009cd0818ae37a793bc3e419ffc4b"


def replace(source, old, new):
    assert source.count(old) == 1, old
    return source.replace(old, new, 1)


def candidate(name):
    content = gzip.decompress((Path("reports/sources") / (DIGEST + ".py.gz")).read_bytes())
    assert hashlib.sha256(content).hexdigest() == DIGEST
    source = content.decode()
    if name == "control":
        return source
    if name == "selective_delivery":
        source = replace(
            source,
            '    actions: list[list[Any]] = [["PASS"] for _ in positions]',
            """    def delivery_action(inv):
        # PLACE deposits one product while retaining inputs assigned to future
        # services. The terminal window still liquidates every carried product.
        needed = {item for item in inv if demand_inputs.get(item, 0)}
        products = [item for item in inv if item in BASE and item not in needed]
        if day < 29 and needed and products:
            item = max(products, key=lambda item: inv[item] * prices[item])
            amount = min(inv[item], shed_room)
            return ["PLACE", item, amount], amount
        return ["DROP"], sum(inv.values())

    actions: list[list[Any]] = [["PASS"] for _ in positions]""",
        )
        source = replace(
            source,
            """            actions[i] = ["DROP"] if home_dist == 0 else move(pos, home)
            if home_dist == 0:
                shed_room -= sum(inv.values())""",
            """            if home_dist == 0:
                actions[i], deposited = delivery_action(inv)
                shed_room -= deposited
            else:
                actions[i] = move(pos, home)
            if home_dist == 0:""",
        )
        source = replace(
            source,
            """        elif load and sum(inv.values()) <= shed_room:
            actions[i] = ["DROP"]
            shed_room -= sum(inv.values())""",
            """        elif load and home_dist == 0 and sum(inv.values()) <= shed_room:
            actions[i], deposited = delivery_action(inv)
            shed_room -= deposited""",
        )
        compile(source, name, "exec")
        return source
    source = replace(
        source,
        '    actions: list[list[Any]] = [["PASS"] for _ in positions]',
        """    # Ordinary end-of-day transfers are free, but liquidity and shared shed
    # capacity can require earlier sale. Preserve the final-day return window.
    delivery_pressure = day == 29 or farm["money"] < max(2000, feed_need * prices["WHEAT"] + 500) or sum(stock.values()) >= 80
    actions: list[list[Any]] = [["PASS"] for _ in positions]""",
    )
    source = replace(
        source,
        'and ((pos in shed_tiles and load >= 3) or load >= p["return_load"] or end_return)',
        'and (end_return or (delivery_pressure and ((pos in shed_tiles and load >= 3) or load >= p["return_load"])))',
    )
    source = replace(
        source, "elif load and home_dist:", "elif load and home_dist and delivery_pressure:"
    )
    source = replace(
        source,
        "elif load and sum(inv.values()) <= shed_room:",
        "elif load and home_dist == 0 and delivery_pressure and sum(inv.values()) <= shed_room:",
    )
    if name == "service_routes":
        source = replace(
            source,
            """                amount = min(
                    shed[required], 3 if required == "WHEAT" else 4, demand_inputs[required]
                )""",
            """                # Count nearby outstanding services, then bound the batch by
                # time to reach the first destination and service its neighborhood.
                nearby = sum(item == required and distance(target, target2) <= 4
                             for target2, _, _, item, _ in tasks)
                service_time = 3 if required == "WHEAT" else 2
                reachable = max(1, (23 - hour - distance(home, target)) // service_time)
                amount = min(shed[required], 6, nearby, reachable, demand_inputs[required])""",
        )
    else:
        assert name == "nightly_pressure"
    compile(source, name, "exec")
    return source


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--name",
        choices=("control", "nightly_pressure", "service_routes", "selective_delivery"),
        default="service_routes",
    )
    parser.add_argument("--seeds", nargs="+", type=int, default=[0, 2001])
    parser.add_argument(
        "--opponents",
        nargs="+",
        default=["data/raw/reference-cok/main.py", "data/raw/reference-seyam/main.py"],
    )
    parser.add_argument("--workers", type=int, default=2)
    parser.add_argument("--output", type=Path, default=Path("data/raw/phase3-logistics.json"))
    args = parser.parse_args()
    content = candidate(args.name).encode()
    digest = hashlib.sha256(content).hexdigest()
    path = Path("data/interim/phase3-logistics") / args.name / digest / "main.py"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
    manifest = {
        **provenance([str(path), *args.opponents]),
        "base_sha256": DIGEST,
        "hypothesis": "Avoid discretionary returns when liquid and below storage capacity; bound input pickup by remaining service opportunities",
        "candidate_snapshot": snapshot(path),
        "name": args.name,
        "complete": False,
        "episodes": [],
    }
    tasks = [
        (str(path), opp, seed, seat, None)
        for opp in args.opponents
        for seed in args.seeds
        for seat in (0, 1)
    ]
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with ProcessPoolExecutor(max_workers=args.workers) as pool:
        for row in pool.map(episode, tasks):
            manifest["episodes"].append(row)
            args.output.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
            print(
                args.name,
                row["opponent"],
                row["seed"],
                row["seat"],
                row["cash"],
                row["opponent_cash"],
                flush=True,
            )
    manifest["complete"] = True
    args.output.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
