"""Test feasible annual watering before harvesting its final growth increment."""

import argparse
import gzip
import hashlib
import json
from concurrent.futures import ProcessPoolExecutor
from copy import deepcopy
from pathlib import Path

from benchmark import episode, provenance, snapshot
from phase2_logistics import replace

BASE = "febe9c76051a11e9ea7700e2d4701722e98274c51c50874ad03e1088b9398d4b"


def build():
    content = gzip.decompress((Path("reports/sources") / (BASE + ".py.gz")).read_bytes())
    assert hashlib.sha256(content).hexdigest() == BASE
    source = content.decode()
    source = replace(
        source,
        "        exhausted = interval and age >= first + (cap - 1) * interval and not yield_units",
        """        # An annual crop gains immediately on WATER. Preserve the last increment
        # only when a worker can still harvest and, on the final day, deliver.
        approach = min(distance(pos, (x, y)) for pos in positions)
        liquidation = min(distance((x, y), home) for home in shed_tiles) + 1 if terminal else 0
        remaining = (23 if terminal else 24) - hour
        if expiry >= 0:
            remaining = min(remaining, expiry - obs["step"])
        water_before_harvest = (
            ripe and not interval and growth and not tile["watered_today"]
            and yield_units < cap and approach + 2 + liquidation <= remaining
        )
        exhausted = interval and age >= first + (cap - 1) * interval and not yield_units""",
    )
    source = replace(
        source,
        '        if not tile["watered_today"] and not terminal and (tile["consecutive_unwatered"] or growth):',
        '        if water_before_harvest or (not tile["watered_today"] and not terminal and (tile["consecutive_unwatered"] or growth)):',
    )
    source = replace(
        source,
        """                p["deadline_boost"]
                if tile["consecutive_unwatered"] and hour >= 15
                else 115
                if tile["consecutive_unwatered"]
                else 65,""",
        """                140 if water_before_harvest else (p["deadline_boost"]
                if tile["consecutive_unwatered"] and hour >= 15
                else 115
                if tile["consecutive_unwatered"]
                else 65),""",
    )
    source = replace(source, "        if ripe:", "        if ripe and not water_before_harvest:")
    compile(source, "harvest_growth", "exec")
    return source


def check():
    from kaggle_environments import make
    from kaggle_environments.envs.kaggriculture import kaggriculture as game

    env = make("kaggriculture", configuration={"seed": 0, "episodeSteps": 720})
    env.reset()
    initial_observation = deepcopy(env.state[0].observation)
    configuration = dict(env.configuration)
    ns = {}
    exec(build(), ns)
    base = {}
    exec(gzip.decompress((Path("reports/sources") / (BASE + ".py.gz")).read_bytes()), base)
    cases = []
    for day, hour, expected in [
        (4, 10, "WATER"),
        (4, 22, "WATER"),
        (4, 23, "HARVEST"),
        (29, 20, "WATER"),
        (29, 21, "HARVEST"),
    ]:
        obs = deepcopy(initial_observation)
        obs.update(day=day, hour=hour, step=24 * day + hour, player=0)
        farm = game._new_farm(10, 0)
        farm["farmer"] = [4, 4]
        obs["farms"][0] = farm
        obs["private"] = {"shed": {}, "seeds": {}, "inventories": [{}]}
        tile = game._new_plant("WHEAT", day - 4, 24)
        tile.update(yield_units=3, consecutive_unwatered=0)
        farm["tiles"][4][4] = tile
        before = base["agent"](deepcopy(obs), configuration)["farmer"]
        result = ns["agent"](deepcopy(obs), configuration)["farmer"]
        assert result == [expected], (day, hour, result)
        if expected == "WATER":
            game._apply_unit_action(farm, obs["private"], 0, result, 10, day, 24, 100)
            assert tile["yield_units"] == 4
            obs.update(hour=hour + 1, step=obs["step"] + 1)
            result2 = ns["agent"](deepcopy(obs), configuration)["farmer"]
            assert result2 == ["HARVEST"], result2
            game._apply_unit_action(farm, obs["private"], 0, result2, 10, day, 24, 100)
            assert obs["private"]["inventories"][0]["WHEAT"] == 4
        cases.append({"day": day, "hour": hour, "base": before, "candidate": result})
    return cases


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--workers", type=int, default=2)
    parser.add_argument("--output", type=Path, default=Path("data/raw/phase3-harvest.json"))
    args = parser.parse_args()
    cases = check()
    if args.check:
        print(json.dumps(cases, indent=2))
        return
    content = build().encode()
    digest = hashlib.sha256(content).hexdigest()
    path = Path("data/interim/phase3-harvest") / digest / "main.py"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
    opponents = ["data/raw/reference-cok/main.py", "data/raw/reference-seyam/main.py"]
    manifest = {
        **provenance([str(path), *opponents]),
        "base_sha256": BASE,
        "hypothesis": "Preserve immediate annual crop growth before harvest when harvesting and terminal delivery remain feasible",
        "candidate_snapshot": snapshot(path),
        "contract_checks": cases,
        "complete": False,
        "episodes": [],
    }
    tasks = [
        (str(path), opp, seed, seat, None)
        for opp in opponents
        for seed in [2000, 2003, 2009, 2013]
        for seat in (0, 1)
    ]
    with ProcessPoolExecutor(max_workers=args.workers) as pool:
        for row in pool.map(episode, tasks):
            manifest["episodes"].append(row)
            args.output.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
            print(
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
