"""Review saved collection panels and verify drought deaths with official helpers.

Runs no games. The final two-action control witness is an explicitly offline
worker-transition diagnostic, excluded from all competitive measurements.
"""

import argparse
import gzip
import hashlib
import json
from collections import Counter
from copy import deepcopy
from pathlib import Path
from statistics import mean, median

import numpy as np

PANELS = {
    "control": "data/raw/breakthrough-opening-mooman.json",
    "market": "data/raw/breakthrough-market-collection-mooman.json",
    "capital": "data/raw/breakthrough-investment-cash-mooman.json",
    "safe": "data/raw/breakthrough-safe-collection-mooman.json",
    "extension": "data/raw/breakthrough-fertilizer-field.json",
}


def read(path):
    path = Path(path)
    if not path.exists():
        path = Path(str(path) + ".gz")
    raw = path.read_bytes()
    if path.suffix == ".gz":
        raw = gzip.decompress(raw)
    return json.loads(raw), hashlib.sha256(raw).hexdigest()


def gap(row):
    return row["cash"] - row["opponent_cash"]


def score(row):
    return float(gap(row) > 0) + 0.5 * (gap(row) == 0)


def sums(rows, field):
    result = Counter()
    for row in rows:
        result.update(row[field])
    return dict(result)


def aggregate(rows):
    return {
        "games": len(rows),
        "wins": sum(gap(row) > 0 for row in rows),
        "draws": sum(gap(row) == 0 for row in rows),
        "score": mean(map(score, rows)),
        "cash_mean": mean(row["cash"] for row in rows),
        "gap_mean": mean(map(gap, rows)),
        "gap_median": median(map(gap, rows)),
        "gap_p10": float(np.quantile(list(map(gap, rows)), 0.1)),
        "losses": sums(rows, "losses"),
        "ledger": sums(rows, "ledger"),
        "realized_actions": sums(rows, "realized_actions"),
        "stderr_turns": sum(row["stderr_turns"] for row in rows),
        "errors": sum(row["statuses"] != ["DONE", "DONE"] for row in rows),
        "runtime_max_seconds": max(row["runtime_max_seconds"] for row in rows),
        "runtime_game_p99_median_seconds": median(row["runtime_p99_seconds"] for row in rows),
    }


def paired(rows, control):
    known = {(row["seed"], row["seat"]): row for row in control}
    changes = {}
    for row in rows:
        base = known[row["seed"], row["seat"]]
        assert row["opponent"] == base["opponent"]
        changes.setdefault(row["seed"], []).append(gap(row) - gap(base))
    values = np.array([mean(v) for v in changes.values()])
    rng = np.random.default_rng(9400)
    bootstrap = rng.choice(values, size=(10000, len(values)), replace=True).mean(axis=1)
    return {
        "paired_mean_gap_change": float(values.mean()),
        "paired_seed_bootstrap_95_interval": list(np.quantile(bootstrap, [0.025, 0.975])),
        "seed_means": {str(seed): mean(values) for seed, values in changes.items()},
        "interpretation": "Descriptive development-panel interval; seats resampled together by seed.",
    }


def water_deaths(row):
    from kaggle_environments.envs.kaggriculture import kaggriculture as game

    replay, digest = read(row["replay_path"])
    seat, events = row["seat"], []
    cfg = replay["configuration"]
    for index in range(24, len(replay["steps"]), 24):
        previous, recorded = replay["steps"][index - 1 : index + 1]
        shared = previous[0]["observation"]
        farm = deepcopy(shared["farms"][seat])
        private = deepcopy(previous[seat]["observation"]["private"])
        action = recorded[seat]["action"] or {}
        units = [action.get("farmer", ["PASS"]), *action.get("hands", [])]
        requests = Counter(work[1] for work in units if work[0] == "PLANT")
        blocked = {
            item for item, count in requests.items() if count > private["seeds"].get(item, 0)
        }
        for worker, work in enumerate(units):
            if work[0] == "PLANT" and work[1] in blocked:
                work = ["PASS"]
            game._apply_unit_action(
                farm,
                private,
                worker,
                work,
                cfg["boardSize"],
                shared["day"],
                cfg["turnsPerDay"],
                cfg["shedCapacity"],
            )
        before = deepcopy(farm["tiles"])
        game._daily_refresh_plants(farm, shared["day"], cfg["turnsPerDay"])
        for y, board_row in enumerate(before):
            for x, tile in enumerate(board_row):
                if not (
                    isinstance(tile, dict)
                    and tile.get("kind") == "PLANT"
                    and not tile["watered_today"]
                    and tile["consecutive_unwatered"] >= 1
                ):
                    continue
                assert farm["tiles"][y][x] == {"kind": "WEED"}
                assert recorded[0]["observation"]["farms"][seat]["tiles"][y][x] == {"kind": "WEED"}
                events.append(
                    {
                        "step": index,
                        "day": shared["day"],
                        "position": [x, y],
                        "crop": tile["crop"],
                        "age": shared["day"] - tile["planted_day"],
                        "planted_day": tile["planted_day"],
                        "held_units": tile["yield_units"],
                        "price_before_refresh": shared["market"]["prices"][tile["crop"]],
                        "max_lifespan_step": tile["max_lifespan_step"],
                    }
                )
    assert len(events) == row["losses"].get("water_deaths", 0), (
        row["seed"],
        seat,
        events,
        row["losses"],
    )
    return {
        "seed": row["seed"],
        "seat": seat,
        "replay_sha256": digest,
        "replay_path": row["replay_path"],
        "events": events,
    }


def control_witness(row):
    from kaggle_environments.envs.kaggriculture import kaggriculture as game

    replay, digest = read(row["replay_path"])
    seat = row["seat"]
    results = {}
    for label in ("recorded", "water_neighbor"):
        start = replay["steps"][598]
        farm = deepcopy(start[0]["observation"]["farms"][seat])
        private = deepcopy(start[seat]["observation"]["private"])
        assert game._farmer_position(farm, 12) == [8, 0]
        actions = []
        for index in (599, 600):
            action = deepcopy(replay["steps"][index][seat]["action"])
            if label == "water_neighbor":
                action["hands"][11] = ["SOUTH"] if index == 599 else ["WATER"]
            actions.append(action["hands"][11])
            for worker, work in enumerate([action["farmer"], *action["hands"]]):
                game._apply_unit_action(farm, private, worker, work, 10, 24, 24, 100)
        game._daily_refresh_plants(farm, 24, 24)
        results[label] = {
            "worker12_actions": actions,
            "worker12_position_before_reset": game._farmer_position(farm, 12),
            "worker12_inventory": private["inventories"][12],
            "tile_8_0": farm["tiles"][0][8],
            "tile_8_1": farm["tiles"][1][8],
        }
    old, new = results["recorded"], results["water_neighbor"]
    assert old["worker12_actions"] == [["HARVEST"], ["SOUTH"]]
    assert old["tile_8_1"] == {"kind": "WEED"}
    assert new["tile_8_1"]["crop"] == "STRAWBERRY"
    assert old["worker12_position_before_reset"] == new["worker12_position_before_reset"]
    assert old["worker12_inventory"].get("STRAWBERRY", 0) + old["tile_8_0"]["yield_units"] == (
        new["worker12_inventory"].get("STRAWBERRY", 0) + new["tile_8_0"]["yield_units"]
    )
    return {
        "classification": "avoidable local scheduler miss; not a season cash counterfactual",
        "offline_counterfactual": True,
        "eligible_for_competitive_scores": False,
        "scope": "Two official worker turns plus plant refresh; recorded other workers; no market or opponent rollout.",
        "seed": row["seed"],
        "seat": seat,
        "replay_sha256": digest,
        "additional_held_berries": new["tile_8_1"]["yield_units"],
        "results": results,
    }


def route_trace(row, source_hash, day, target):
    """Replay observed policy inputs only; never advance an environment."""
    replay, digest = read(row["replay_path"])
    raw = gzip.decompress((Path("reports/sources") / f"{source_hash}.py.gz").read_bytes())
    assert hashlib.sha256(raw).hexdigest() == source_hash
    namespace = {}
    exec(raw.decode(), namespace)
    seat, calls = row["seat"], []
    for index in range(day * 24, (day + 1) * 24):
        step = replay["steps"][index]
        obs = deepcopy(step[0]["observation"])
        obs.update(deepcopy(step[seat]["observation"]))
        obs["player"] = seat
        action = namespace["agent"](obs, replay["configuration"])
        plans = namespace["_DAILY_ROUTES"][seat]["plans"]
        routes = {
            str(worker): plan["ops"]
            for worker, plan in plans.items()
            if any(position == target for position, _, _ in plan["ops"])
        }
        calls.append(
            {
                "step": index,
                "matches_recorded_action": action == replay["steps"][index + 1][seat]["action"],
                "target_routes": routes,
                "stats": dict(namespace["_DAILY_ROUTE_STATS"]),
                "urgent_products": sorted(namespace["urgent_products"](obs))
                if "urgent_products" in namespace
                else [],
            }
        )
    assert all(call["matches_recorded_action"] for call in calls), "Inexact diagnostic policy trace"
    return {
        "source_sha256": source_hash,
        "replay_sha256": digest,
        "day": day,
        "target": target,
        "matched_observed_decisions": len(calls),
        "calls": calls,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("reports/results/breakthrough-safe-collection-review.json"),
    )
    args = parser.parse_args()
    groups, inputs, identities, provenance = {}, {}, {}, {}
    for panel, path in PANELS.items():
        document, digest = read(path)
        inputs[path] = digest
        provenance[path] = {
            key: document[key]
            for key in (
                "revision",
                "environment_version",
                "interpreter_sha256",
                "harness_sha256",
                "executable_bundles",
            )
        }
        if panel == "safe":
            assert len(document["episodes"]) == 48, "Review requires completed predeclared screen"
        for row in document["episodes"]:
            identity = document["candidates"][row["candidate"]]
            name = identity["name"]
            if panel == "control" and name != "capacity_budget":
                continue
            if panel == "extension" and name != "capacity_budget":
                continue
            label = "control_extension" if panel == "extension" else name
            identities[label] = identity
            groups.setdefault(label, []).append(row)
    result = {
        "method": __doc__,
        "manifest_sha256": inputs,
        "identities": identities,
        "provenance": provenance,
        "analysis_source_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "summaries": {name: aggregate(rows) for name, rows in groups.items()},
        "comparisons": {},
        "verified_water_deaths": {},
        "control_witnesses": [],
    }
    base = groups["capacity_budget"]
    for name, rows in groups.items():
        if name != "control_extension":
            result["comparisons"][name] = paired(rows, base)
        result["verified_water_deaths"][name] = [
            water_deaths(row) for row in rows if row["losses"].get("water_deaths")
        ]
    for row in groups["control_extension"]:
        if row["losses"].get("water_deaths"):
            result["control_witnesses"].append(control_witness(row))
    result["observed_policy_traces"] = [
        route_trace(
            next(
                row
                for row in groups["control_extension"]
                if row["seed"] == 5018 and row["seat"] == 0
            ),
            identities["control_extension"]["sha256"],
            24,
            (8, 1),
        ),
        route_trace(
            next(
                row
                for row in groups["capacity_market_safe"]
                if row["seed"] == 5000 and row["seat"] == 0
            ),
            identities["capacity_market_safe"]["sha256"],
            20,
            (4, 0),
        ),
    ]
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(args.output)


if __name__ == "__main__":
    main()
