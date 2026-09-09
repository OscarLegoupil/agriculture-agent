"""Reproduce frozen validation diagnosis from archived records and saved replays.

Recorded actions are applied to copied observations with the official unit
transition helper. This reconstructs harvest quantities; it runs no new games.
"""

import argparse
import hashlib
import json
from collections import Counter
from copy import deepcopy
from pathlib import Path
from statistics import mean, median

import numpy as np
from evidence_io import read_result
from kaggle_environments.envs.kaggriculture import kaggriculture as game

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument(
    "--incumbent", type=Path, default=Path("reports/results/phase2-validation-incumbent.json.gz")
)
parser.add_argument(
    "--challenger", type=Path, default=Path("reports/results/phase2-validation-challenger.json.gz")
)
parser.add_argument("--replays", type=Path, default=Path("reports/replays/phase2-validation"))
parser.add_argument(
    "--output", type=Path, default=Path("reports/results/phase2-validation-diagnosis.json")
)
parser.add_argument(
    "--check", action="store_true", help="Check existing measurements without writing output"
)
args = parser.parse_args()
datasets = {n: read_result(getattr(args, n)) for n in ["incumbent", "challenger"]}
for name, data in datasets.items():
    missing = [
        e
        for e in data["episodes"]
        if e["seed"] in (2000, 2001)
        and e["seat"] == 0
        and not (args.replays / Path(e["replay_path"].replace("\\", "/")).name).is_file()
    ]
    if missing:
        candidate_hash = Path(data["candidate_snapshot"].replace("\\", "/")).name[:64]
        executable = f"data/interim/diagnosis-{name}/main.py"
        opponents = " ".join(sorted({e["opponent"] for e in data["episodes"]}))
        parser.error(
            f"Missing {len(missing)} saved {name} replays in {args.replays}. This command never runs new games. Regenerate separately after fetching the pinned references:\nuv run python scripts/restore_candidate.py {candidate_hash} --output {executable}\nuv run python scripts/benchmark.py --candidate {executable} --opponents {opponents} --seeds 2000 2001 --workers 2 --output data/raw/diagnosis-{name}-replays.json --replays {args.replays.as_posix()}"
        )
verified_replays = 0
result = {
    "scope": "Post-selection validation diagnosis, no additional games and no policy changes. Shop paths can differ between whole-policy interventions.",
    "groups": {},
    "representatives": [],
}
for name, data in datasets.items():
    assert data["complete"] and len(data["episodes"]) == 512
    result["groups"][name] = {}
    for opponent in sorted({e["opponent"] for e in data["episodes"]}):
        episodes = [e for e in data["episodes"] if e["opponent"] == opponent]
        gaps = [e["cash"] - e["opponent_cash"] for e in episodes]
        ledger = {
            key: mean(e["ledger"].get(key, 0) for e in episodes)
            for key in sorted({key for e in episodes for key in e["ledger"]})
        }
        actions = {
            key: mean(e["realized_actions"].get(key, 0) for e in episodes)
            for key in sorted({key for e in episodes for key in e["realized_actions"]})
        }
        losses = {
            key: mean(e["losses"].get(key, 0) for e in episodes)
            for key in sorted({key for e in episodes for key in e["losses"]})
        }
        result["groups"][name][opponent] = {
            "games": len(episodes),
            "wins": sum(g > 0 for g in gaps),
            "mean_cash": mean(e["cash"] for e in episodes),
            "mean_gap": mean(gaps),
            "median_gap": median(gaps),
            "p10_gap": float(np.quantile(gaps, 0.1)),
            "max_crops": mean(max(r["crops"] for r in e["daily"]) for e in episodes),
            "ledger": ledger,
            "actions": actions,
            "losses": losses,
        }
    for episode in [e for e in data["episodes"] if e["seed"] in (2000, 2001) and e["seat"] == 0]:
        path = args.replays / Path(episode["replay_path"].replace("\\", "/")).name
        content = path.read_bytes()
        replay = json.loads(content)
        production = [Counter(), Counter()]
        snapshots = []
        for day in [0, 1, 2, 3, 5, 8, 10, 12, 15, 20, 25, 29]:
            obs = replay["steps"][day * 24 + 5][0]["observation"]
            farms = []
            for farm in obs["farms"]:
                composition = Counter(
                    t.get("animal", t.get("crop", t.get("kind")))
                    for row in farm["tiles"]
                    for t in row
                    if isinstance(t, dict)
                )
                farms.append(
                    {
                        "cash": farm["money"],
                        "hands": len(farm["hands"]),
                        "land": len(farm["unlocked_quadrants"]),
                        "composition": dict(composition),
                    }
                )
            snapshots.append(
                {"day": day, "hour": 5, "shops": obs["town"]["unlocked_shops"], "farms": farms}
            )
        for step, following in zip(replay["steps"], replay["steps"][1:], strict=False):
            obs = step[0]["observation"]
            for seat in [0, 1]:
                action = following[seat].get("action") or {}
                actions = [action.get("farmer", ["PASS"]), *action.get("hands", [])]
                if not any(a and a[0] == "HARVEST" for a in actions):
                    continue
                farm = deepcopy(obs["farms"][seat])
                private = deepcopy(step[seat]["observation"]["private"])
                demanded = Counter(a[1] for a in actions if len(a) > 1 and a[0] == "PLANT")
                blocked = {c for c, n in demanded.items() if n > private["seeds"].get(c, 0)}
                for index, act in enumerate(actions):
                    if len(act) > 1 and act[0] == "PLANT" and act[1] in blocked:
                        act = ["PASS"]
                    before = (
                        Counter(private["inventories"][index])
                        if index < len(private["inventories"])
                        else Counter()
                    )
                    game._apply_unit_action(
                        farm,
                        private,
                        index,
                        act,
                        len(farm["tiles"]),
                        obs["day"],
                        replay["configuration"].get("turnsPerDay", 24),
                        replay["configuration"].get("shedCapacity", 100),
                    )
                    if act and act[0] == "HARVEST" and index < len(private["inventories"]):
                        delta = Counter(private["inventories"][index]) - before
                        production[seat].update(delta)
        # These products are not purchased as inputs. Exact harvested units
        # must reconcile with recorded sales plus terminal unsold inventories.
        private = replay["steps"][-1][episode["seat"]]["observation"]["private"]
        for product in ("CARROT", "TOMATO", "MELON", "STRAWBERRY", "MILK", "WOOL", "EGG"):
            unsold = private["shed"].get(product, 0) + sum(
                i.get(product, 0) for i in private["inventories"]
            )
            sold = episode["ledger"].get("units:SELL:" + product, 0)
            if production[episode["seat"]][product] != sold + unsold:
                raise AssertionError(f"Harvest/sales reconciliation failed: {path} {product}")
        verified_replays += 1
        if "cok" not in episode["opponent"]:
            continue
        result["representatives"].append(
            {
                "policy": name,
                "seed": episode["seed"],
                "seat": 0,
                "opponent": episode["opponent"],
                "replay": path.as_posix(),
                "replay_sha256": hashlib.sha256(content).hexdigest(),
                "cash": episode["cash"],
                "opponent_cash": episode["opponent_cash"],
                "snapshots": snapshots,
                "harvested_units": [dict(p) for p in production],
            }
        )
content = (json.dumps(result, indent=2) + "\n").encode()
if args.check:
    existing = json.loads(args.output.read_bytes())
    for representative in existing["representatives"]:
        representative["replay"] = representative["replay"].replace("\\", "/")
    if existing != result:
        raise AssertionError("Saved diagnosis differs from reconstructed measurements")
else:
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(content)
print(
    f"Verified {verified_replays} replays; diagnostic SHA256 {hashlib.sha256(content).hexdigest()}"
)
