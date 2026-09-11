"""Reconstruct saved fleet/Mooman losses; run no policies or new games."""

import argparse
import hashlib
import json
from collections import Counter
from copy import deepcopy
from pathlib import Path
from statistics import mean

import numpy as np
from phase3_field_economics import analyze

FLEET = "9400f9b0cdaa02d268ab9e234779d17013f2facf5f5517698bdfdb04671464b7"
BASE = "64fe323936dc9494add413eb956b0294658a88efe28572332c94676c68a09325"


def rows(manifest, digest):
    return [
        row
        for row in manifest["episodes"]
        if manifest["candidates"][row["candidate"]]["sha256"] == digest
    ]


def aggregate(episodes):
    gaps = [row["cash"] - row["opponent_cash"] for row in episodes]
    keys = set().union(*(row["ledger"] for row in episodes))
    return dict(
        games=len(episodes),
        wins=sum(gap > 0 for gap in gaps),
        draws=sum(gap == 0 for gap in gaps),
        mean_cash=mean(row["cash"] for row in episodes),
        mean_gap=mean(gaps),
        median_gap=float(np.median(gaps)),
        p10_gap=float(np.quantile(gaps, 0.1)),
        ledger_means={
            key: mean(row["ledger"].get(key, 0) for row in episodes) for key in sorted(keys)
        },
        losses=dict(sum((Counter(row["losses"]) for row in episodes), Counter())),
        errors=sum(row["statuses"] != ["DONE", "DONE"] for row in episodes),
    )


def reconstruct(path):
    from kaggle_environments.envs.kaggriculture import kaggriculture as game

    original_unit, original_market = game._apply_unit_action, game._process_market
    farm_seats = {}
    actions, daily_actions = (
        [Counter(), Counter()],
        [[Counter() for _ in range(30)] for _ in range(2)],
    )

    def unit(farm, private, worker, action, *rest):
        seat = farm_seats.setdefault(id(farm), len(farm_seats))
        position = game._farmer_position(farm, worker)
        if position is None:
            return original_unit(farm, private, worker, action, *rest)
        x, y = position

        def snapshot():
            return (
                tuple(game._farmer_position(farm, worker)),
                deepcopy(farm["tiles"][y][x]),
                dict(private["inventories"][worker]),
                dict(private["shed"]),
                dict(private["seeds"]),
            )

        before = snapshot()
        value = original_unit(farm, private, worker, action, *rest)
        op = action[0] if action else "PASS"
        kind = "success:" if before != snapshot() else "idle:" if op == "PASS" else "failed:"
        actions[seat][kind + op] += 1
        daily_actions[seat][rest[1]][kind + op] += 1
        return value

    def market(state, env):
        value = original_market(state, env)
        farm_seats.clear()
        return value

    game._apply_unit_action, game._process_market = unit, market
    try:
        result = analyze(path)
    finally:
        game._apply_unit_action, game._process_market = original_unit, original_market
    replay = json.loads(path.read_bytes())
    for seat, player in enumerate(result["players"]):
        cohorts = set()
        for step in replay["steps"]:
            for y, row in enumerate(step[0]["observation"]["farms"][seat]["tiles"]):
                for x, tile in enumerate(row):
                    if isinstance(tile, dict) and tile.get("crop") == "STRAWBERRY":
                        cohorts.add((x, y, tile["planted_day"]))
        ideal_units = 0
        for _, _, born in cohorts:
            farm = game._new_farm(10, 3000)
            farm["tiles"][0][0] = game._new_plant("STRAWBERRY", born, 24)
            for day in range(born, 29):
                tile = farm["tiles"][0][0]
                tile.update(watered_today=True, fertilized_until_day=day)
                game._daily_refresh_plants(farm, day, 24)
                ideal_units += tile["yield_units"]
                tile["yield_units"] = 0
        player["berry_births"] = dict(sorted(Counter(born for _, _, born in cohorts).items()))
        player["same_berry_cohorts_perfect_saleable_units"] = ideal_units
        player["realized_actions"] = actions[seat]
        for day, entry in enumerate(player["daily"]):
            entry["day"] = day
            entry["realized_actions"] = daily_actions[seat][day]
            entry.pop("shops")
            entry.pop("market")
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("reports/results/breakthrough-fleet-mooman-diagnosis.json"),
    )
    args = parser.parse_args()
    paths = [
        Path("data/raw/breakthrough-fleet-mooman.json"),
        Path("data/raw/breakthrough-race-mooman.json"),
    ]
    manifests = [json.loads(path.read_bytes()) for path in paths]
    assert all(manifest["complete"] for manifest in manifests)
    assert manifests[0]["interpreter_sha256"] == manifests[1]["interpreter_sha256"]
    opponent = "data/raw/reference-mooman/main.py"
    assert manifests[0]["hashes"][opponent] == manifests[1]["hashes"][opponent]
    fleet, baseline = rows(manifests[0], FLEET), rows(manifests[1], BASE)
    indexed = {(row["seed"], row["seat"]): row for row in baseline}
    assert len(fleet) == len(baseline) == len(indexed) == 16
    seeds = sorted({row["seed"] for row in fleet})
    deltas = []
    for seed in seeds:
        same_seed = []
        for row in fleet:
            if row["seed"] == seed:
                before = indexed[(seed, row["seat"])]
                assert row["configuration"] == before["configuration"]
                same_seed.append(
                    row["cash"] - row["opponent_cash"] - before["cash"] + before["opponent_cash"]
                )
        deltas.append(mean(same_seed))
    rng = np.random.default_rng(20260910)
    samples = np.asarray(deltas)[rng.integers(0, len(seeds), size=(10000, len(seeds)))].mean(axis=1)
    result = dict(
        method="Saved official games only. Paired cash intervals resample entire seeds with both seats. Cohort bounds assume perfect watering, fertilization, immediate collection, unchanged assets and exogenous prices; no labor/input feasibility or unchanged opposing behavior is claimed.",
        inputs={str(path): hashlib.sha256(path.read_bytes()).hexdigest() for path in paths},
        source_sha256=dict(incumbent=BASE, fleet=FLEET, opponent=manifests[0]["hashes"][opponent]),
        environment_version=manifests[0]["environment_version"],
        interpreter_sha256=manifests[0]["interpreter_sha256"],
        declared_panel=manifests[0]["declared_panel"],
        incumbent=aggregate(baseline),
        fleet=aggregate(fleet),
        paired_cash_gap_gain=mean(deltas),
        paired_cash_gap_ci95=list(np.quantile(samples, [0.025, 0.975])),
        bootstrap=dict(seed=20260910, replicates=10000, unit="whole seed, both seats retained"),
        replays=[],
    )
    selected = [
        next(row for row in fleet if row["seed"] == seed and row["seat"] == 0)
        for seed in (5000, 5007)
    ]
    selected.append(indexed[(5000, 0)])
    for row in selected:
        diagnosis = reconstruct(Path(row["replay_path"]))
        assert diagnosis["players"][row["seat"]]["realized_actions"] == row["realized_actions"]
        diagnosis.update(seed=row["seed"], candidate_seat=row["seat"])
        result["replays"].append(diagnosis)
        print(Path(row["replay_path"]).name, "verified", flush=True)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, separators=(",", ":")) + "\n", encoding="utf-8")
    print(args.output)


if __name__ == "__main__":
    main()
