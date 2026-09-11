"""Diagnose frozen crop-admission games without running another match.

Official action/market helpers reconstruct saved cash transitions. The decision
probe executes the frozen source only against its own recorded observations.
"""

import gzip
import hashlib
import json
import runpy
import sys
from collections import Counter
from copy import deepcopy
from pathlib import Path

from phase3_field_economics import analyze

BASE = "fca083cdb5ac82dc4ad39a4227ef60ca57c948f819b565804aa706994f8e61ba"
EARLY = "9a83bb475173e00d1b5e2b28dada9c472e9e751139a5493ddbf1d3e5eb6a4652"


def replay_path(digest, seed, seat=0):
    return Path(f"reports/replays/breakthrough/{digest}-reference-mooman-main-{seed}-{seat}.json")


def timeline(replay, seat=0):
    seen, births, land, daily = set(), [], [], []
    old_land = 1
    for step in replay["steps"]:
        obs = deepcopy(step[0]["observation"])
        obs.update(step[seat]["observation"])
        farm = obs["farms"][seat]
        if len(farm["unlocked_quadrants"]) != old_land:
            land.append(dict(day=obs["day"], hour=obs["hour"], cash=farm["money"]))
            old_land = len(farm["unlocked_quadrants"])
        composition = Counter()
        for y, row in enumerate(farm["tiles"]):
            for x, tile in enumerate(row):
                if not isinstance(tile, dict):
                    continue
                composition[tile.get("crop", tile.get("animal", tile["kind"]))] += 1
                if tile.get("kind") == "PLANT":
                    identity = (x, y, tile["crop"], tile["planted_day"])
                    if identity not in seen:
                        seen.add(identity)
                        births.append(
                            dict(
                                day=obs["day"],
                                hour=obs["hour"],
                                x=x,
                                y=y,
                                crop=tile["crop"],
                                born=tile["planted_day"],
                            )
                        )
        if obs["hour"] == 0:
            daily.append(
                dict(
                    day=obs["day"],
                    cash=farm["money"],
                    composition=dict(composition),
                    wheat_seeds=obs["private"]["seeds"]["WHEAT"],
                    town=obs["town"]["unlocked_shops"],
                )
            )
    return dict(births=births, land=land, daily=daily)


def first_decisions(replay):
    source = gzip.decompress(Path(f"reports/sources/{EARLY}.py.gz").read_bytes())
    assert hashlib.sha256(source).hexdigest() == EARLY
    namespace = {}
    exec(source, namespace)
    original = namespace["crop_opportunity_values"]
    calls, mismatches = [], []

    def values(*args):
        result = original(*args)
        if args[0]["step"] == 72:
            calls.append(dict(target=args[-1], funded=dict(args[2]), scores=dict(result)))
        return result

    namespace["crop_opportunity_values"] = values
    decisions = []
    for index, step in enumerate(replay["steps"][:120]):
        obs = deepcopy(step[0]["observation"])
        decision = namespace["agent"](obs, replay["configuration"])
        if decision != replay["steps"][index + 1][0]["action"]:
            mismatches.append(index)
        if index == 72:
            decisions.append(
                dict(
                    step=index,
                    money=obs["farms"][0]["money"],
                    seeds=obs["private"]["seeds"],
                    decision=decision,
                )
            )
    assert not mismatches, mismatches
    return dict(
        calls=calls,
        decisions=decisions,
        verified_recorded_actions=120,
        mismatches=mismatches,
        modeled_berry_calendar=namespace["opportunity_schedule"]("STRAWBERRY", 3, True),
    )


def main():
    output = dict(
        method=(
            "Read-only saved-game diagnosis. Matched seeds do not fix realized shops: "
            "official day-local RNG draws weeds on empty sites before choosing a shop. "
            "Action/market reconstruction samples no random transitions. No future "
            "observation is used by the replayed decision probe."
        ),
        sources=dict(base=BASE, early=EARLY),
        inputs={},
        town_divergence=[],
        representative={},
    )
    for seed in range(5000, 5008):
        for seat in (0, 1):
            pair = []
            for digest in (BASE, EARLY):
                path = replay_path(digest, seed, seat)
                raw = path.read_bytes()
                output["inputs"][str(path)] = hashlib.sha256(raw).hexdigest()
                replay = json.loads(raw)
                pair.append(replay)
                if seed == 5007 and seat == 0:
                    economic = analyze(path)
                    for player in economic["players"]:
                        for row in player["daily"]:
                            row.pop("market")
                    output["representative"][digest] = dict(
                        timeline=timeline(replay), economic=economic
                    )
                    if digest == EARLY:
                        output["representative"][digest]["decision_probe"] = first_decisions(replay)
            first = next(
                (
                    i
                    for i, (a, b) in enumerate(zip(pair[0]["steps"], pair[1]["steps"], strict=True))
                    if a[0]["observation"]["town"] != b[0]["observation"]["town"]
                ),
                None,
            )
            output["town_divergence"].append(
                dict(
                    seed=seed,
                    seat=seat,
                    first_step=first,
                    base=None
                    if first is None
                    else pair[0]["steps"][first][0]["observation"]["town"],
                    early=None
                    if first is None
                    else pair[1]["steps"][first][0]["observation"]["town"],
                )
            )
    path = Path("reports/results/breakthrough-opportunity-diagnosis.json.gz")
    path.write_bytes(
        gzip.compress((json.dumps(output, separators=(",", ":")) + "\n").encode(), mtime=0)
    )
    print(path)
    print(
        "Town path first divergence:",
        Counter(row["first_step"] for row in output["town_divergence"]),
    )


def financed_prefix():
    """Bounded official continuation witness; this does not report match scores."""
    from kaggle_environments import make
    from kaggle_environments.agent import get_last_callable

    build = runpy.run_path("experiments/crop_opportunity_financed.py")["build"]
    reference = Path("data/raw/reference-mooman/main.py")
    assert (
        hashlib.sha256(reference.read_bytes()).hexdigest()
        == "4332662941c5eb6cb79c8d0acdb75ddf0d9c2ad66a7cb002787d3b99ffe19ded"
    )
    parent = gzip.decompress(Path(f"reports/sources/{EARLY}.py.gz").read_bytes()).decode()
    output = dict(
        method="Official seed5007 responding-Mooman prefixes, both seats, 216 actions per episode. No state intervention or terminal match result.",
        opponent=str(reference),
        opponent_sha256=hashlib.sha256(reference.read_bytes()).hexdigest(),
        episodes=[],
    )
    for label, source in (("early", parent), ("financed", build())):
        for seat in (0, 1):
            own = get_last_callable(source)
            other = runpy.run_path(str(reference))["agent"]
            env = make("kaggriculture", configuration={"seed": 5007})
            env.reset()
            births, daily, purchases = [], [], []
            deaths = escapes = failed_plants = 0
            for index in range(216):
                views = [env._Environment__get_shared_state(p).observation for p in (0, 1)]
                before = deepcopy(views[seat]["farms"][seat])
                positions = [before["farmer"], *before["hands"]]
                action = own(views[seat], env.configuration)
                rival_action = other(views[1 - seat], env.configuration)
                work = [action["farmer"], *action["hands"]]
                requested = Counter(row[1] for row in work if row[0] == "PLANT")
                assert all(
                    n <= views[seat]["private"]["seeds"].get(crop, 0)
                    for crop, n in requested.items()
                )
                env.step([action, rival_action] if seat == 0 else [rival_action, action])
                observed = env._Environment__get_shared_state(seat).observation
                farm = observed["farms"][seat]
                for position, task in zip(positions, work, strict=True):
                    if task[0] == "PLANT":
                        tile = farm["tiles"][position[1]][position[0]]
                        success = isinstance(tile, dict) and tile.get("crop") == task[1]
                        failed_plants += not success
                        if success and index >= 72:
                            births.append([index // 24, index % 24, task[1], position])
                for y, row in enumerate(before["tiles"]):
                    for x, tile in enumerate(row):
                        after = farm["tiles"][y][x]
                        if isinstance(tile, dict):
                            deaths += (
                                tile.get("kind") == "PLANT"
                                and isinstance(after, dict)
                                and after.get("kind") == "WEED"
                            )
                            escapes += "animal" in tile and not (
                                isinstance(after, dict) and "animal" in after
                            )
                if len(farm["unlocked_quadrants"]) > len(before["unlocked_quadrants"]):
                    purchases.append([index // 24, index % 24, farm["money"]])
                if observed["hour"] == 0:
                    daily.append(
                        dict(
                            day=index // 24,
                            cash=farm["money"],
                            seeds=dict(observed["private"]["seeds"]),
                            composition=dict(
                                Counter(
                                    t.get("crop", t.get("animal", t["kind"]))
                                    for row in farm["tiles"]
                                    for t in row
                                    if isinstance(t, dict)
                                )
                            ),
                        )
                    )
            output["configuration"] = dict(env.configuration)
            output["episodes"].append(
                dict(
                    label=label,
                    source_sha256=hashlib.sha256(source.encode()).hexdigest(),
                    seat=seat,
                    births=births,
                    daily=daily,
                    land_purchases=purchases,
                    deaths=deaths,
                    escapes=escapes,
                    failed_plants=failed_plants,
                )
            )
    path = Path("reports/results/breakthrough-financed-prefix.json.gz")
    path.write_bytes(
        gzip.compress((json.dumps(output, separators=(",", ":")) + "\n").encode(), mtime=0)
    )
    print(path)


if __name__ == "__main__":
    if "--financed-prefix" in sys.argv:
        financed_prefix()
    else:
        main()
