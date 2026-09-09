"""Test funded herd expansion after establishing the initial melon cohort."""

import argparse
import gzip
import hashlib
import json
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

from benchmark import episode, provenance, snapshot
from phase2_logistics import replace

BASE = "dbd2a8418b57573cb6084712bfbcd2d18245fac83fcf18bc1ab7c39345b5d955"


def build(name):
    content = gzip.decompress((Path("reports/sources") / (BASE + ".py.gz")).read_bytes())
    assert hashlib.sha256(content).hexdigest() == BASE
    source = content.decode()
    old = "    if day < 8:\n        desired = dict(COW=2, SHEEP=2, GOOSE=0)"
    if name == "cohort_funded":
        new = """    # Retain the opening cohort before allowing the existing marginal
    # investment and cash/feed checks to choose additional productive animals.
    if day < 8 and (day < 3 or crops["MELON"] < 12):
        desired = dict(COW=2, SHEEP=2, GOOSE=0)"""
    else:
        assert name == "staged_cows"
        new = """    if day < 8:
        # Release one additional cow slot per two days once the initial crop
        # cohort exists, limiting simultaneous maturity and feeding obligations.
        cap = 2 + max(0, day - 2) // 2 if crops["MELON"] >= 12 else 2
        desired = dict(COW=cap, SHEEP=2, GOOSE=0)"""
    source = replace(source, old, new)
    compile(source, name, "exec")
    return source


def measured_episode(args):
    row = episode(args)
    replay = json.loads(Path(row["replay_path"]).read_bytes())
    row["first_expansion_cow"] = None
    for previous, state in zip(replay["steps"], replay["steps"][1:], strict=False):
        obs = state[row["seat"]]["observation"]
        farm = obs["farms"][row["seat"]]
        cows = [
            t
            for line in farm["tiles"]
            for t in line
            if isinstance(t, dict) and t.get("animal") == "COW"
        ]
        if len(cows) > 2:
            row["first_expansion_cow"] = {
                "placed_day": max(t["placed_day"] for t in cows),
                "observation_hour": obs["hour"],
                "cash_before": previous[row["seat"]]["observation"]["farms"][row["seat"]]["money"],
                "cash_after": farm["money"],
            }
            break
    return row


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--names", nargs="+", default=["cohort_funded", "staged_cows"])
    parser.add_argument("--seeds", type=int, nargs="+", default=[0, 2001])
    parser.add_argument("--workers", type=int, default=2)
    parser.add_argument("--output", type=Path, default=Path("data/raw/phase3-investment.json"))
    args = parser.parse_args()
    opponents = ["data/raw/reference-cok/main.py", "data/raw/reference-seyam/main.py"]
    manifest = {
        **provenance(opponents),
        "base_sha256": BASE,
        "hypothesis": "Earlier animal cohorts can add production events while preserving the initial crop cohort and existing feed/cash admission checks",
        "candidates": {},
        "complete": False,
        "episodes": [],
    }
    tasks = []
    for name in args.names:
        content = build(name).encode()
        digest = hashlib.sha256(content).hexdigest()
        path = Path("data/interim/phase3-investment") / name / digest / "main.py"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
        manifest["candidates"][str(path)] = {
            "name": name,
            "sha256": digest,
            "snapshot": snapshot(path),
        }
        tasks.extend(
            (str(path), opponent, seed, seat, "data/raw/phase3-investment-replays")
            for opponent in opponents
            for seed in args.seeds
            for seat in (0, 1)
        )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with ProcessPoolExecutor(max_workers=args.workers) as pool:
        for row in pool.map(measured_episode, tasks):
            manifest["episodes"].append(row)
            args.output.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
            print(
                manifest["candidates"][row["candidate"]]["name"],
                row["opponent"],
                row["seed"],
                row["seat"],
                row["cash"],
                row["opponent_cash"],
                row["first_expansion_cow"],
                flush=True,
            )
    manifest["complete"] = True
    args.output.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
