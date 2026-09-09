"""Compare daily feed deadlines with targeted preservation of banked production."""

import argparse
import gzip
import hashlib
import json
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

from benchmark import episode, provenance, snapshot
from phase2_logistics import replace

BASE = "64fe323936dc9494add413eb956b0294658a88efe28572332c94676c68a09325"


def build(mode, priority="escape"):
    raw = gzip.decompress((Path("reports/sources") / (BASE + ".py.gz")).read_bytes())
    assert hashlib.sha256(raw).hexdigest() == BASE
    source = raw.decode()
    needle = 'if op == "FEED" and board[target[1]][target[0]]["consecutive_unfed"] > 0'
    if mode == "daily":
        source = replace(source, needle, 'if op == "FEED"')
    elif mode == "banked":
        insertion = """        valuable_production = set()
        for x, y, animal in animals:
            _, first, interval, cap, product, _ = ANIMALS[animal["animal"]]
            production_age = day + 1 - animal["placed_day"] - first
            bonus = min(animal.get("pending_care_bonus", 0), max(0, cap - animal["yield_units"] - 1))
            if (production_age >= 0 and production_age % interval == 0
                    and bonus * prices[product] > prices["WHEAT"] + 4):
                valuable_production.add((x, y))
"""
        source = replace(source, "        pending = {", insertion + "        pending = {")
        source = replace(
            source,
            needle,
            'if op == "FEED" and (board[target[1]][target[0]]["consecutive_unfed"] > 0 or target in valuable_production)',
        )
    else:
        raise ValueError(mode)
    if priority == "escape":
        source = replace(
            source,
            "candidates.append((route[-1], target, route))",
            'candidates.append((0 if board[target[1]][target[0]]["consecutive_unfed"] > 0 else 1, route[-1], target, route))',
        )
        source = replace(
            source,
            "_, target, (_, i, home, fetching, _) = min(candidates)",
            "_, _, target, (_, i, home, fetching, _) = min(candidates)",
        )
    elif priority != "slack":
        raise ValueError(priority)
    compile(source, "feed_production_deadline", "exec")
    return source


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workers", type=int, default=2)
    parser.add_argument("--output", type=Path, default=Path("data/raw/phase4-care-corrected.json"))
    parser.add_argument("--priority", choices=("escape", "slack"), default="escape")
    args = parser.parse_args()
    candidates = {}
    for mode in ("daily", "banked"):
        content = build(mode, args.priority).encode()
        digest = hashlib.sha256(content).hexdigest()
        path = Path("data/interim/phase4-care") / mode / digest / "main.py"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
        candidates[str(path)] = {"mode": mode, "sha256": digest, "snapshot": snapshot(path)}
    opponents = ["data/raw/reference-cok/main.py", "data/raw/reference-seyam/main.py"]
    manifest = {
        **provenance([*candidates, *opponents]),
        "base_sha256": BASE,
        "priority": args.priority,
        "hypothesis": "Separate immediate loss of banked production from daily feeding needed to accumulate care bonuses",
        "candidates": candidates,
        "complete": False,
        "episodes": [],
    }
    tasks = [
        (
            candidate,
            opp,
            seed,
            seat,
            "reports/replays/phase4-care" if seed == 3063 and "cok" in opp else None,
        )
        for candidate in candidates
        for opp in opponents
        for seed in [3000, 3017, 3042, 3063]
        for seat in (0, 1)
    ]
    with ProcessPoolExecutor(max_workers=args.workers) as pool:
        for row in pool.map(episode, tasks):
            manifest["episodes"].append(row)
            args.output.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
            print(
                candidates[row["candidate"]]["mode"],
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
