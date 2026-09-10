"""Inspect funded crop tasks in frozen expanded-farm replays; run no games."""

import argparse
import gzip
import hashlib
import json
from collections import Counter
from copy import deepcopy
from pathlib import Path

from kaggle_environments.envs.kaggriculture import kaggriculture as game

HASH = "909b5a1f8e9b6dbec3998f28a10a8b7f95fbd43175cc03be9bf5f58d0a78c5b1"


def build():
    raw = gzip.decompress((Path("reports/sources") / (HASH + ".py.gz")).read_bytes())
    assert hashlib.sha256(raw).hexdigest() == HASH
    source = raw.decode()
    for old, new in [
        (
            'task(x, y, "PLANT", 42, arg=crop)',
            'task(x, y, "PLANT", 120 if 8 <= day <= 16 and hour <= 22 else 42, arg=crop)',
        ),
        ('task(x, y, "DIG", 35)', 'task(x, y, "DIG", 90 if 8 <= day <= 16 and hour <= 21 else 35)'),
    ]:
        assert source.count(old) == 1
        source = source.replace(old, new)
    compile(source, "funded_commissioning", "exec")
    return source


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--build", action="store_true", help="Freeze the single authorized commissioning candidate"
    )
    parser.add_argument(
        "--screen", action="store_true", help="Run the declared 16-game development screen"
    )
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument(
        "--output", type=Path, default=Path("data/raw/phase4-commissioning-screen.json")
    )
    args = parser.parse_args()
    if args.build:
        raw = build().encode()
        digest = hashlib.sha256(raw).hexdigest()
        path = Path("data/interim/phase4-commissioning") / digest / "main.py"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(raw)
        print(path)
        return
    if args.screen:
        assert 1 <= args.workers <= 4
        assert not args.output.exists(), "Do not overwrite an existing experiment"
        from strategy_screen import screen

        candidate = build()
        assert hashlib.sha256(candidate.encode()).hexdigest() == (
            "902ce3828c450bba73223a68fd72ad9455dd0db28234274cc1299c1943c7eaa5"
        )
        screen(
            {"funded_commissioning": candidate},
            [f"data/raw/reference-{name}/main.py" for name in ("seyam", "cok")],
            [3000, 3017, 3042, 3063],
            args.output,
            args.workers,
            inputs=[__file__],
            replays="reports/replays/phase4-commissioning-screen",
        )
        return
    raw = gzip.decompress((Path("reports/sources") / (HASH + ".py.gz")).read_bytes())
    assert hashlib.sha256(raw).hexdigest() == HASH
    source = raw.decode()
    needle = "        tasks.append(((x, y), op, value, item, arg))"
    assert source.count(needle) == 1
    source = source.replace(
        needle, needle + "\n        _TRACE.append(((x, y), op, value, item, arg))"
    )
    assert source.count("    for i in order:") == 1
    source = source.replace(
        "    for i in order:",
        "    _META.update(matched=matched, deadlines=deadline_actions)\n    for i in order:",
    )
    ns = {}
    exec(source, ns)
    result = []
    paths = sorted(Path("reports/replays/phase4-commissioning").glob(HASH + "*.json"))
    assert paths, (
        "Reproduce the authorized seed3063 frozen candidate with benchmark.py --replays first"
    )
    for path in paths:
        replay = json.loads(path.read_bytes())
        seat = int(path.stem[-1])
        daily = {}
        witnesses = []
        mismatch = 0
        for step, (before, after) in enumerate(
            zip(replay["steps"], replay["steps"][1:], strict=False)
        ):
            obs = deepcopy(before[0]["observation"])
            obs.update(deepcopy(before[seat]["observation"]))
            obs.update(player=seat, step=step)
            if not 10 <= obs["day"] <= 20:
                continue
            farm = obs["farms"][seat]
            day = obs["day"]
            record = daily.setdefault(day, Counter())
            ns["_TRACE"] = []
            ns["_META"] = {}
            action = ns["agent"](deepcopy(obs), replay["configuration"])
            mismatch += action != after[seat]["action"]
            tasks = ns["_TRACE"]
            counts = Counter(
                t.get("crop", t.get("animal", "other"))
                for row in farm["tiles"]
                for t in row
                if isinstance(t, dict)
            )
            if obs["hour"] == 0:
                record.update({"start:" + c: n for c, n in counts.items()})
                record["start:cash"] = farm["money"]
                record["start:seeds"] = sum(obs["private"]["seeds"].values())
            record["funded_plant_task_turns"] += sum(t[1] == "PLANT" for t in tasks)
            record["funded_dig_task_turns"] += sum(t[1] == "DIG" and t[2] == 35 for t in tasks)
            work = [action["farmer"], *action["hands"]]
            record.update("requested:" + a[0] for a in work)
            positions = [farm["farmer"], *farm["hands"]]
            planting = Counter(a[1] for a in work if a[0] == "PLANT")
            for idx, pos in enumerate(positions):
                for target, op, value, _, crop in tasks:
                    if list(target) != pos or op != "PLANT" or work[idx][0] == "PLANT":
                        continue
                    if obs["private"]["seeds"].get(crop, 0) <= planting[crop]:
                        continue
                    probe_farm = deepcopy(farm)
                    private = deepcopy(obs["private"])
                    game._apply_unit_action(
                        probe_farm, private, idx, ["PLANT", crop], 10, day, 24, 100
                    )
                    planted = probe_farm["tiles"][pos[1]][pos[0]]
                    if not isinstance(planted, dict) or planted.get("crop") != crop:
                        continue
                    record["immediate_plant_bypasses"] += 1
                    inventory = obs["private"]["inventories"][idx]
                    record["immediate_plant_bypasses_low_load"] += sum(inventory.values()) < 5
                    if len(witnesses) < 40:
                        witnesses.append(
                            {
                                "day": day,
                                "hour": obs["hour"],
                                "worker": idx,
                                "position": pos,
                                "crop": crop,
                                "chosen": work[idx],
                                "plant_priority": value,
                                "cash": farm["money"],
                                "matched_target": ns["_META"]["matched"].get(idx),
                                "matched_tasks": [
                                    t for t in tasks if t[0] == ns["_META"]["matched"].get(idx)
                                ],
                                "deadline_reserved": idx in ns["_META"]["deadlines"],
                                "seeds": obs["private"]["seeds"],
                                "inventory": obs["private"]["inventories"][idx],
                            }
                        )
        witness_step = replay["steps"][11 * 24 + 7]
        witness_farm = deepcopy(witness_step[0]["observation"]["farms"][seat])
        witness_private = deepcopy(witness_step[seat]["observation"]["private"])
        assert witness_farm["farmer"] == [4, 2]
        before_seed = witness_private["seeds"]["WHEAT"]
        witness_actions = [["PLANT", "WHEAT"], ["WATER"], ["EAST"], ["COLLECT_FERTILIZER"]]
        for operation in witness_actions:
            game._apply_unit_action(witness_farm, witness_private, 0, operation, 10, 11, 24, 100)
        assert witness_farm["tiles"][2][4]["crop"] == "WHEAT"
        assert witness_farm["tiles"][2][4]["watered_today"]
        assert witness_private["seeds"]["WHEAT"] == before_seed - 1
        assert witness_private["inventories"][0].get("FERTILIZER", 0) > 0
        game._daily_refresh_plants(witness_farm, 11, 24)
        assert witness_farm["tiles"][2][4]["crop"] == "WHEAT"
        result.append(
            {
                "replay": str(path),
                "replay_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                "official_commissioning_witness": {
                    "day": 11,
                    "hour": 7,
                    "worker": 0,
                    "actions": witness_actions,
                    "survives_day_end": True,
                    "fertilizer_collected": witness_private["inventories"][0].get("FERTILIZER", 0),
                    "scope": "Copied official state; proves local feasibility, not full-policy outcome",
                },
                "action_mismatches": mismatch,
                "daily": daily,
                "immediate_plant_witnesses": witnesses,
            }
        )
    Path("reports/results/phase4-commissioning.json").write_text(
        json.dumps(result, indent=2) + "\n"
    )
    for row in result:
        print(row["replay"], "mismatches", row["action_mismatches"])
        print(json.dumps(row["daily"]))
        print(json.dumps(row["immediate_plant_witnesses"][:8]))


if __name__ == "__main__":
    main()
