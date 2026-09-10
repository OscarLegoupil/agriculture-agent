"""Test executable opening cohorts and fertilizer timing on the frozen challenger."""

import argparse
import gzip
import hashlib
import json
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

from benchmark import episode, provenance, snapshot
from phase2_logistics import replace

BASE_HASH = "0098d9e4f77e2420cb4a09abd47e49f5160009cd0818ae37a793bc3e419ffc4b"


def build(name):
    content = gzip.decompress((Path("reports/sources") / (BASE_HASH + ".py.gz")).read_bytes())
    assert hashlib.sha256(content).hexdigest() == BASE_HASH
    source = content.decode("utf-8")
    if "fert" in name:
        # The planning assumption and physical controller must agree: annual
        # growth is credited by WATER, so post-water fertilizer is not today's yield.
        source = replace(
            source,
            "            and growth\n",
            "            and growth\n            and interval > 0\n",
        )
        source = replace(
            source,
            "crop, day, forecast[crop] / (1 + planned[crop] * 0.025), fert_price, use_fert",
            "crop, day, forecast[crop] / (1 + planned[crop] * 0.025), fert_price, use_fert and CROPS[crop][3] > 0",
        )
    if "startup" in name:
        source = replace(
            source,
            "def agent(",
            "PARAMS.update(cows=10, sheep=4, geese=0, hands=12)\n\n\ndef agent(",
        )
        source = replace(
            source,
            "    purchase = None",
            "    if day < 8:\n        desired = dict(COW=2, SHEEP=2, GOOSE=0)\n    purchase = None",
        )
        source = replace(
            source,
            'if day <= p["animal_stop"]:',
            'if day <= p["animal_stop"] and sum(stock[a] for a in ANIMALS) < 2:',
        )
        source = replace(
            source,
            "    workload = len(plants) * 1.4 + len(animals) * 4.5",
            "    workload = max(48 if day < 2 else 0, len(plants) * 1.4 + len(animals) * 4.5)",
        )
        source = replace(
            source,
            "if cash > cost + 1000:",
            'if cash > cost + max(300, feed_need * prices["WHEAT"] + 150):',
        )
        source = replace(
            source,
            "cash > CROPS[crop][0] + 250",
            "cash > CROPS[crop][0] + (30 if day < 2 else 200)",
        )
        source = replace(
            source,
            "        crop = max(values, key=lambda c: values[c])",
            """        # Short crops bridge the first long cohort's startup costs.
        # Later recurring cohorts must arrive early enough to repay before liquidation.
        if day < 15:
            target = "WHEAT" if planned["WHEAT"] < 7 else "MELON" if day < 3 else "STRAWBERRY"
            current_value = crop_value(target, day, prices[target], fert_price, use_fert and (CROPS[target][3] > 0 if "fert" in OPENING_NAME else True))
            if current_value > 0:
                values[target] = max(1, max(values.values()) + 1)
        crop = max(values, key=lambda c: values[c])""",
        )
        source = replace(source, "def agent(", f"OPENING_NAME = {name!r}\n\n\ndef agent(")
        source = replace(
            source,
            "                yield_units >= desired_yield\n",
            '                yield_units >= desired_yield\n                or (crop == "WHEAT" and (cash < 600 or stock["WHEAT"] < feed_need))\n',
        )
    if "reserve" in name:
        source = replace(
            source,
            "            reserve = max(0, min(12, len(plants) // 2) - carried[item])",
            """            applications = 0
            for _, _, plant in plants:
                _, first, _, interval, cap = CROPS[plant["crop"]]
                if not interval or prices[plant["crop"]] <= fert_price * 0.7 + 10:
                    continue
                first_day = plant["planted_day"] + first
                event = first_day + max(0, math.ceil((day + 1 - first_day) / interval)) * interval
                last_day = first_day + (cap - 1) * interval
                if event <= min(day + 3, 29, last_day) and plant["fertilized_until_day"] < event - 1:
                    applications += 1
            reserve = max(0, min(12, applications) - carried[item])""",
        )
    if name.endswith("10") or name.endswith("11"):
        hands = int(name[-2:])
        source = replace(source, "def agent(", f"PARAMS.update(hands={hands})\n\n\ndef agent(")
    assert name in (
        "fert",
        "startup",
        "startup_fert",
        "startup_fert_reserve",
        "startup_fert_reserve10",
        "startup_fert_reserve11",
    )
    compile(source, name, "exec")
    return source


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--names", nargs="+", default=["fert", "startup", "startup_fert"])
    parser.add_argument("--seeds", type=int, nargs="+", default=[0, 2001])
    parser.add_argument("--workers", type=int, default=3)
    parser.add_argument("--output", type=Path, default=Path("data/raw/phase3-startup.json"))
    args = parser.parse_args()
    opponents = [f"data/raw/reference-{name}/main.py" for name in ("seyam", "cok")]
    manifest = {
        **provenance([*opponents, "scripts/phase3_startup.py"]),
        "base_sha256": BASE_HASH,
        "candidates": {},
        "complete": False,
        "episodes": [],
    }
    tasks = []
    for name in args.names:
        content = build(name).encode()
        digest = hashlib.sha256(content).hexdigest()
        path = Path("data/interim/phase3-startup") / name / digest / "main.py"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
        manifest["candidates"][str(path)] = {
            "name": name,
            "sha256": digest,
            "snapshot": snapshot(path),
        }
        tasks.extend(
            (str(path), opponent, seed, seat, None)
            for opponent in opponents
            for seed in args.seeds
            for seat in (0, 1)
        )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with ProcessPoolExecutor(max_workers=args.workers) as pool:
        for row in pool.map(episode, tasks):
            manifest["episodes"].append(row)
            args.output.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
            print(
                manifest["candidates"][row["candidate"]]["name"],
                row["opponent"],
                row["seed"],
                row["seat"],
                row["cash"],
                row["opponent_cash"],
                flush=True,
            )
    for path, metadata in manifest["candidates"].items():
        assert hashlib.sha256(Path(path).read_bytes()).hexdigest() == metadata["sha256"]
    manifest["complete"] = True
    args.output.write_text(json.dumps(manifest, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
