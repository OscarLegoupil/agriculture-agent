"""Official-environment screen of compatible service bundles and input routes."""

import argparse
import hashlib
import json
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

from benchmark import episode, provenance, snapshot

INCUMBENT = Path("submissions/20260909-v7/main.py")
DIGEST = "750f123073865347efd3b9c4b72022ff9923f4130c929ac76c1b0742374b09ee"

BUNDLE_FUNCTION = """    tasks_by_target = defaultdict(list)
    for entry in tasks:
        tasks_by_target[entry[0]].append(entry)

    def service_score(target, op, value, required, inv, cost):
        remaining = (23 if day == 29 else 24) - hour
        if cost > remaining:
            return 0.0
        available = dict(inv)
        if required:
            if not available.get(required, 0):
                available[required] = min(shed.get(required, 0), 3)
            available[required] = max(0, available.get(required, 0) - 1)
        compatible = []
        if op in ("WATER", "FERTILIZE", "FEED", "CARE", "HARVEST", "COLLECT_FERTILIZER"):
            for _, other_op, other_value, other_required, _ in tasks_by_target[target]:
                if other_op == op or other_op not in ("WATER", "FERTILIZE", "FEED", "CARE", "HARVEST", "COLLECT_FERTILIZER"):
                    continue
                if other_required:
                    if not available.get(other_required, 0):
                        continue
                    available[other_required] -= 1
                compatible.append(other_value)
            x, y = target
            tile = board[y][x]
            if op == "FEED" and isinstance(tile, dict) and not tile.get("cared_today", True) and p["care"]:
                compatible.append(60)
        compatible.sort(reverse=True)
        score = value / (cost + 1.5)
        cumulative = value
        for count, extra in enumerate(compatible[:3], start=1):
            if cost + count > remaining:
                break
            cumulative += extra * 0.65
            score = max(score, cumulative / (cost + count + 1.5))
        if ROUTE_VALUE and required in ("WHEAT", "FERTILIZER"):
            nearby = sorted((distance(target, t), v) for t, _, v, item, _ in tasks if t != target and item == required)
            if nearby and available.get(required, 0) and cost + nearby[0][0] + 1 <= remaining:
                score += 0.15 * nearby[0][1] / (cost + nearby[0][0] + 2.5)
        return score

    actions: list[list[Any]] = [["PASS"] for _ in positions]"""


def replace(source, old, new):
    assert source.count(old) == 1, old
    return source.replace(old, new, 1)


def candidate(name):
    content = INCUMBENT.read_bytes()
    assert hashlib.sha256(content).hexdigest() == DIGEST
    source = content.decode()
    source = replace(
        source,
        "        tasks.append(((x, y), op, value, item, arg))",
        '        if op == "PLANT" and hour >= 23:\n            return\n        tasks.append(((x, y), op, value, item, arg))',
    )
    source = replace(
        source,
        '    actions: list[list[Any]] = [["PASS"] for _ in positions]',
        BUNDLE_FUNCTION.replace("ROUTE_VALUE", str(name == "input_routes")),
    )
    source = replace(
        source,
        "                matrix[i][c] = min(matrix[i][c], -value / (travel + 1.5))",
        "                matrix[i][c] = min(matrix[i][c], -service_score(target, op, value, required_item, inventories[i], travel))",
    )
    source = replace(
        source,
        "            score = value / (cost + 1.5)",
        "            score = service_score(target, op, value, required, inv, cost)\n            if score <= 0:\n                continue",
    )
    if name == "input_routes":
        source = replace(
            source,
            '                    shed[required], 3 if required == "WHEAT" else 4, demand_inputs[required]',
            '                    shed[required], max(1, min(6, (24 - hour) // 3)) if required == "WHEAT" else 4, demand_inputs[required]',
        )
    assert name in ("service_bundles", "input_routes")
    compile(source, name, "exec")
    return source


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--names", nargs="+", default=["service_bundles", "input_routes"])
    parser.add_argument("--seeds", type=int, nargs="+", default=[17, 103])
    parser.add_argument(
        "--opponents",
        nargs="+",
        default=[
            "data/raw/reference-lonespear/main.py",
            "data/raw/reference-gzm/main.py",
            "data/raw/reference-seyam/main.py",
            "data/raw/reference-cok/main.py",
        ],
    )
    parser.add_argument("--workers", type=int, default=3)
    parser.add_argument("--output", type=Path, default=Path("data/raw/phase2-work-bundles.json"))
    args = parser.parse_args()
    manifest = {
        **provenance([str(INCUMBENT), *args.opponents]),
        "hypothesis": "Compatible tasks and reachable input service routes improve assignment beyond independent immediate tasks",
        "candidates": {},
        "episodes": [],
    }
    tasks = []
    for name in args.names:
        content = candidate(name).encode()
        digest = hashlib.sha256(content).hexdigest()
        path = Path("data/interim/phase2-work-bundles") / name / digest / "main.py"
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
            args.output.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
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
