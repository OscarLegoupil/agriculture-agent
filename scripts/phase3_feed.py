"""Test feed cohorts valued against displaced crops and observed obligations."""

import argparse
import gzip
import hashlib
import json
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

from benchmark import episode, provenance, snapshot
from phase2_logistics import replace

BASE = "febe9c76051a11e9ea7700e2d4701722e98274c51c50874ad03e1088b9398d4b"


def build(valuation="controller"):
    content = gzip.decompress((Path("reports/sources") / (BASE + ".py.gz")).read_bytes())
    assert hashlib.sha256(content).hexdigest() == BASE
    source = content.decode()
    source = replace(
        source,
        "        # Short crops bridge the first long cohort's startup costs.",
        "        economic_values = dict(values)\n        # Short crops bridge the first long cohort's startup costs.",
    )
    source = replace(
        source,
        "        crop = max(values, key=lambda c: values[c])",
        """        if 8 <= day <= 25:
            herd_obligation = len(animals) + sum(stock[a] for a in ANIMALS)
            horizon = min(5, 29 - day)
            # Normal unfertilized wheat reaches four units on age four, then
            # needs replanting. The existing shortage controller can harvest at
            # age two; value that shorter two-unit cycle when its trigger holds.
            early_harvest = cash < 600 or stock["WHEAT"] < feed_need
            units, cycle = (2, 3) if early_harvest else (4, 5)
            target_wheat = math.ceil(max(0, herd_obligation * cycle - max(0, stock["WHEAT"] - herd_obligation)) / units)
            arriving = 0
            for _, _, plant in plants:
                if plant["crop"] != "WHEAT":
                    continue
                age = day - plant["planted_day"]
                remaining_growth = max(0, 4 - max(1, age))
                if max(0, (2 if early_harvest else 4) - age) <= horizon:
                    arriving += min(units, plant["yield_units"] + remaining_growth)
            deficit = herd_obligation * horizon - stock["WHEAT"] - arriving
            feed_price = max(prices["WHEAT"], forecast["WHEAT"]) + 1
            feed_value = crop_value("WHEAT", day, feed_price, fert_price, False)
            alternative = max(value for crop, value in economic_values.items() if crop != "WHEAT")
            if deficit > 0 and planned["WHEAT"] < target_wheat and feed_value > max(0, alternative):
                values["WHEAT"] = max(values.values()) + 1
        crop = max(values, key=lambda c: values[c])""",
    )
    if valuation == "controller":
        source = replace(
            source,
            '            feed_value = crop_value("WHEAT", day, feed_price, fert_price, False)',
            '            feed_value = (units * feed_price - CROPS["WHEAT"][0] - 5 * 4) / cycle if early_harvest else crop_value("WHEAT", day, feed_price, fert_price, False)',
        )
    else:
        assert valuation == "maturity"
    compile(source, "prospective_feed", "exec")
    return source


def measured_episode(args):
    row = episode(args)
    terminal = row["daily"][-1]
    row["wheat_harvest_from_balance"] = None
    if terminal["shed"] == terminal["carried"] == row["losses"].get("overflow_units", 0) == 0:
        row["wheat_harvest_from_balance"] = (
            row["ledger"].get("units:SELL:WHEAT", 0)
            + row["realized_actions"].get("success:FEED", 0)
            - row["ledger"].get("units:BUY_PRODUCT:WHEAT", 0)
        )
    return row


def probe_existing_replays():
    """Compare valuations off-policy on already recorded incumbent observations."""
    from copy import deepcopy

    ns = []
    for valuation in ("maturity", "controller"):
        s = build(valuation).replace(
            '                values["WHEAT"] = max(values.values()) + 1',
            '                OVERRIDES.append((day, early_harvest, feed_value, alternative))\n                values["WHEAT"] = max(values.values()) + 1',
        )
        n = {"OVERRIDES": []}
        exec(s, n)
        ns.append(n)
    rows = []
    paths = sorted(Path("data/raw/phase3-opening-diagnostic-replays").glob("*.json"))
    if len(paths) != 4:
        raise FileNotFoundError(
            "Expected four saved opening diagnostic replays; restore data/raw/phase3-opening-diagnostic-replays before using --probe"
        )
    for p in paths:
        replay = json.loads(p.read_bytes())
        seat = int(p.stem[-1])
        changed = 0
        for n in ns:
            n["OVERRIDES"].clear()
        for idx, step in enumerate(replay["steps"][:-1]):
            obs = deepcopy(step[0]["observation"])
            obs.update(step[seat]["observation"])
            obs["step"] = idx
            obs["player"] = seat
            actions = [n["agent"](deepcopy(obs), replay["configuration"]) for n in ns]
            changed += actions[0] != actions[1]
        rows.append(
            {
                "replay": p.name,
                "changed_actions": changed,
                "overrides": [len(n["OVERRIDES"]) for n in ns],
                "early_overrides": [sum(x[1] for x in n["OVERRIDES"]) for n in ns],
            }
        )
    return rows


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seeds", nargs="+", type=int, default=[0, 2001])
    parser.add_argument("--workers", type=int, default=2)
    parser.add_argument("--valuation", choices=("maturity", "controller"), default="controller")
    parser.add_argument("--output", type=Path, default=Path("data/raw/phase3-feed-corrected.json"))
    parser.add_argument(
        "--probe",
        action="store_true",
        help="Compare valuations on existing diagnostic replays without running games",
    )
    args = parser.parse_args()
    if args.probe:
        print(json.dumps(probe_existing_replays(), indent=2))
        return
    opponents = ["data/raw/reference-cok/main.py", "data/raw/reference-seyam/main.py"]
    content = build(args.valuation).encode()
    digest = hashlib.sha256(content).hexdigest()
    path = Path("data/interim/phase3-feed") / digest / "main.py"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
    manifest = {
        **provenance([str(path), *opponents]),
        "base_sha256": BASE,
        "valuation": args.valuation,
        "hypothesis": "Grow additional feed only against observed herd obligations when purchase replacement value beats displaced crop value",
        "candidate_snapshot": snapshot(path),
        "complete": False,
        "episodes": [],
    }
    tasks = [
        (str(path), opponent, seed, seat, None)
        for opponent in opponents
        for seed in args.seeds
        for seat in (0, 1)
    ]
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with ProcessPoolExecutor(max_workers=args.workers) as pool:
        for row in pool.map(measured_episode, tasks):
            manifest["episodes"].append(row)
            args.output.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
            print(
                row["opponent"],
                row["seed"],
                row["seat"],
                row["cash"],
                row["opponent_cash"],
                row["wheat_harvest_from_balance"],
                flush=True,
            )
    manifest["complete"] = True
    args.output.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
