"""Test a bounded local feed reserve alongside remote carried wheat."""

import argparse
import gzip
import hashlib
import json
from collections import Counter
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

from benchmark import episode, provenance, snapshot
from phase2_logistics import replace

BASES = {
    "v8": "64fe323936dc9494add413eb956b0294658a88efe28572332c94676c68a09325",
    "banked": "401b58a64d12a3df82ae9157a8d12a0d1e99c10c273fecb96f0d399501a9c6d4",
}


def build(base="v8"):
    digest = BASES[base]
    raw = gzip.decompress((Path("reports/sources") / (digest + ".py.gz")).read_bytes())
    assert hashlib.sha256(raw).hexdigest() == digest
    source = raw.decode()
    insertion = """    # Remote carried wheat cannot satisfy a near-term shed pickup.
    # Keep a small depot only for unfed animals still reachable after purchase.
    depot_floor = 0
    if day < 29 and farm["money"] >= 1000 and feed_need:
        serviceable = sum(
            not tile["fed_today"] and 1 + min(
                distance(pos, home) + 1 + distance(home, (x, y)) + 1
                for pos in positions for home in shed_tiles
            ) <= 24 - hour
            for x, y, tile in animals
        )
        depot_floor = min(3, serviceable)
    # Every currently carried unit could be dropped before market execution.
    # This bound does not spend room made by a future pickup or pending sale.
    depot_room = max(0, cfg.get("shedCapacity", 100) - sum(shed.values()) - sum(carried.values()))
"""
    source = replace(
        source,
        '    fert_price = prices["FERTILIZER"]',
        '    fert_price = prices["FERTILIZER"]' + "\n" + insertion,
    )
    source = replace(
        source,
        '        if item == "FERTILIZER" and p["fertilize"] and day < 29 and cash >= 1000:',
        '        if item == "WHEAT":\n            reserve = max(reserve, depot_floor)\n        if item == "FERTILIZER" and p["fertilize"] and day < 29 and cash >= 1000:',
    )
    source = replace(
        source,
        '    buy_feed = max(0, feed_need - stock["WHEAT"])',
        '    depot_shortage = max(0, min(depot_floor - shed.get("WHEAT", 0), depot_room, int(max(0, cash - 1000) // (prices["WHEAT"] + 1))))\n    buy_feed = max(0, feed_need - stock["WHEAT"], depot_shortage)',
    )
    compile(source, "local_feed_depot", "exec")
    return source


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--output", type=Path, default=Path("data/raw/phase4-depot.json"))
    parser.add_argument(
        "--diagnose", action="store_true", help="Read completed records and replays; run no games"
    )
    args = parser.parse_args()
    if args.diagnose:
        from phase3_field_execution import analyse
        from phase4_execution import service_decomposition

        data = json.loads(args.output.read_bytes())
        assert data.get("complete")
        result = []
        for row in data["episodes"]:
            if not row["replay_path"] or row["seat"] != 0:
                continue
            path = Path(row["replay_path"])
            measured = analyse(path)
            service = service_decomposition(json.loads(path.read_bytes()))[0]
            lost = Counter()
            for event in service["production_eve_feed_losses"]:
                lost[event["product"]] += event["extra_units_if_fed"]
            result.append(
                {
                    "base": data["candidates"][row["candidate"]]["base"],
                    "cash": measured["final_cash"],
                    "harvested": measured["harvested"],
                    "service": service,
                    "banked_units_lost": dict(lost),
                    "ledger": row["ledger"],
                    "losses": row["losses"],
                }
            )
        Path("reports/results/phase4-depot-diagnosis.json").write_text(
            json.dumps(result, indent=2) + "\n"
        )
        return
    candidates = {}
    for base in BASES:
        raw = build(base).encode()
        digest = hashlib.sha256(raw).hexdigest()
        path = Path("data/interim/phase4-depot") / base / digest / "main.py"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(raw)
        candidates[str(path)] = {
            "base": base,
            "base_sha256": BASES[base],
            "sha256": digest,
            "snapshot": snapshot(path),
        }
    opponents = ["data/raw/reference-cok/main.py", "data/raw/reference-seyam/main.py"]
    manifest = {
        **provenance([*candidates, *opponents]),
        "hypothesis": "A small serviceable shed feed reserve corrects the spatial fungibility assumption without counting unexecuted inputs",
        "candidates": candidates,
        "complete": False,
        "episodes": [],
    }
    tasks = [
        (c, o, seed, seat, "reports/replays/phase4-depot" if seed == 3063 and "cok" in o else None)
        for c in candidates
        for o in opponents
        for seed in [3000, 3017, 3042, 3063]
        for seat in (0, 1)
    ]
    with ProcessPoolExecutor(max_workers=args.workers) as pool:
        for row in pool.map(episode, tasks):
            manifest["episodes"].append(row)
            args.output.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
            print(
                candidates[row["candidate"]]["base"],
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
