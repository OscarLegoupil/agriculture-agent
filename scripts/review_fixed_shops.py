"""Audit saved offline fixed-shop controls and contrasts; run no new games."""

import argparse
import gzip
import json
from collections import Counter
from copy import deepcopy
from pathlib import Path
from statistics import mean
from types import SimpleNamespace

if __package__:
    from .diagnose_fixed_shops import LABEL, control_comparison, digest, read_bytes
else:
    from diagnose_fixed_shops import LABEL, control_comparison, digest, read_bytes


def town_consumption(replay, schedule):
    """Count demand with the official helper; no worker or random transition runs."""
    from kaggle_environments.envs.kaggriculture import kaggriculture as game
    from kaggle_environments.utils import structify

    state = structify(deepcopy(replay["steps"][0]))
    initial = dict(state[0].observation.market.inventory)
    config = replay["configuration"]
    env = SimpleNamespace(configuration=structify(config))
    interval = config["townShopUnlockInterval"] * config["turnsPerDay"]
    for step in range(len(replay["steps"]) - 1):
        state[0].observation.town["unlocked_shops"] = schedule[: step // interval]
        game._town_consume(env, state, step)
    return {
        item: amount - state[0].observation.market.inventory[item]
        for item, amount in initial.items()
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=Path("data/raw/offline-fixed-shops.json"))
    parser.add_argument(
        "--output", type=Path, default=Path("reports/results/breakthrough-fixed-shops.json")
    )
    args = parser.parse_args()
    raw = read_bytes(args.input)
    manifest = json.loads(raw)
    assert manifest["complete"] and manifest["competitive_score_eligible"] is False
    assert manifest["evidence_kind"] == "offline_counterfactual" and "episodes" not in manifest
    from kaggle_environments.envs.kaggriculture import kaggriculture as game

    assert (
        digest(Path(game.__file__).read_bytes())
        == manifest["source_provenance"]["interpreter_sha256"]
    )
    expected = {case["case_id"] for case in manifest["planned_cases"]}
    rows = {case["case_id"]: case for case in manifest["counterfactual_cases"]}
    assert len(rows) == len(manifest["counterfactual_cases"]) == 16 and set(rows) == expected
    output = {
        **LABEL,
        "method": "Hash-check all saved archives, verify donor controls against full recorded observations/actions, and decompose cash gaps along explicitly identified policy/town paths. Direct demand counts use the pinned official _town_consume helper only. No new policy execution or game.",
        "input_sha256": digest(raw),
        "analysis_sha256": digest(Path(__file__).read_bytes()),
        "runner_sha256": manifest["runner_sha256"],
        "source_provenance": manifest["source_provenance"],
        "donor_schedules": {name: donor["schedule"] for name, donor in manifest["donors"].items()},
        "cases": {},
        "paired_seat_decompositions": {},
        "seed_decompositions": {},
    }
    for identifier, row in rows.items():
        archived = Path(row["replay_path"]).read_bytes()
        assert digest(archived) == row["replay_archive_sha256"]
        unpacked = gzip.decompress(archived)
        assert digest(unpacked) == row["replay_uncompressed_sha256"]
        wrapped = json.loads(unpacked)
        assert wrapped["competitive_score_eligible"] is False and "steps" not in wrapped
        replay = wrapped["offline_replay"]
        assert replay["configuration"] == row["configuration"]
        assert row["statuses"] == ["DONE", "DONE"] and row["resolved_seed"] == row["seed"]
        donor = manifest["donors"][row["donor"]]
        if row["is_donor_policy_control"]:
            assert control_comparison(replay, donor) == row["donor_policy_control"]
        interval = (
            row["configuration"]["townShopUnlockInterval"] * row["configuration"]["turnsPerDay"]
        )
        for step, states in enumerate(replay["steps"]):
            for state in states:
                assert (
                    state["observation"]["town"]["unlocked_shops"]
                    == donor["schedule"][: step // interval]
                )
        seat = row["seat"]
        receipts = {k[7:]: v for k, v in row["candidate_ledger"].items() if k.startswith("income:")}
        expenses = {
            k[8:]: v for k, v in row["candidate_ledger"].items() if k.startswith("expense:")
        }
        assert row["final_cash_candidate_opponent"][0] == (
            row["configuration"]["startingMoney"] + sum(receipts.values()) - sum(expenses.values())
        )
        units = {
            k[11:]: v for k, v in row["candidate_ledger"].items() if k.startswith("units:SELL:")
        }
        own_diagnostics = row["runtime_by_seat"][str(seat)]
        control = row["donor_policy_control"]
        entry = {
            "replay_archive_sha256": row["replay_archive_sha256"],
            "gap": row["cash_gap"],
            "cash_candidate_opponent": row["final_cash_candidate_opponent"],
            "control": control,
            "control_accepted": None
            if control is None
            else all(
                control[k] for k in ("step_count_matches", "observations_match", "actions_match")
            ),
            "runtime_by_seat": row["runtime_by_seat"],
            "candidate_stderr_turns": own_diagnostics["stderr_turns"],
            "income": receipts,
            "expenses": expenses,
            "sale_units": units,
            "composition_checkpoints": {},
        }
        for step in (360, 480, 624, 719):
            obs = replay["steps"][step][seat]["observation"]
            farm = obs["farms"][seat]
            entry["composition_checkpoints"][str(step)] = {
                "cash": farm["money"],
                "composition": dict(
                    Counter(
                        t.get("crop", t.get("animal", t["kind"]))
                        for tiles in farm["tiles"]
                        for t in tiles
                        if isinstance(t, dict)
                    )
                ),
            }
        if row["is_donor_policy_control"]:
            entry["direct_town_consumption"] = town_consumption(replay, donor["schedule"])
            entry["historical_cash_candidate_opponent"] = donor["recorded_final_cash"]
            entry["historical_candidate_stderr_turns"] = donor["recorded_stderr_turns"]
            if not entry["control_accepted"]:
                previous = json.loads(read_bytes(donor["replay_path"]))
                step = control["first_action_difference"]
                entry["failed_control_details"] = {
                    "action_observation_day": previous["steps"][step - 1][seat]["observation"][
                        "day"
                    ],
                    "action_observation_hour": previous["steps"][step - 1][seat]["observation"][
                        "hour"
                    ],
                    "historical_action": previous["steps"][step][seat]["action"],
                    "counterfactual_action": replay["steps"][step][seat]["action"],
                    "opponent_action_matches": previous["steps"][step][1 - seat]["action"]
                    == replay["steps"][step][1 - seat]["action"],
                }
        output["cases"][identifier] = entry
    for seed in (5000, 5001):
        seed_rows = []
        for seat in (0, 1):
            ff, cf, fc, cc = (
                output["cases"][f"{seed}-{seat}-{town}-town-{policy}"]
                for town, policy in (
                    ("fleet", "fleet"),
                    ("fleet", "cereal"),
                    ("cereal", "fleet"),
                    ("cereal", "cereal"),
                )
            )
            clean_path = (
                ff["control_accepted"]
                and cc["control_accepted"]
                and all(
                    not diagnostics["stderr_turns"]
                    for r in (ff, fc, cc)
                    for diagnostics in r["runtime_by_seat"].values()
                )
            )
            contrast = {
                "historical_diagonal_control_accepted": ff["control_accepted"]
                and cc["control_accepted"],
                "town_first_path_accepted": clean_path,
                "town_first_path": {
                    "town_change_with_fleet_policy": fc["gap"] - ff["gap"],
                    "policy_change_with_cereal_town": cc["gap"] - fc["gap"],
                    "diagonal_sum": cc["gap"] - ff["gap"],
                },
                "opposite_path_has_runtime_fallback": any(
                    r["candidate_stderr_turns"] for r in (ff, cf, cc)
                ),
                "descriptive_opposite_path": {
                    "policy_change_with_fleet_town": cf["gap"] - ff["gap"],
                    "town_change_with_cereal_policy": cc["gap"] - cf["gap"],
                    "interaction": (cc["gap"] - fc["gap"]) - (cf["gap"] - ff["gap"]),
                },
                "direct_demand_change": {
                    item: cc["direct_town_consumption"][item] - value
                    for item, value in ff["direct_town_consumption"].items()
                },
                "candidate_receipt_changes_on_town_first_path": {
                    "town_change_with_fleet_policy": {
                        item: fc["income"].get(item, 0) - ff["income"].get(item, 0)
                        for item in fc["income"].keys() | ff["income"].keys()
                    },
                    "policy_change_with_cereal_town": {
                        item: cc["income"].get(item, 0) - fc["income"].get(item, 0)
                        for item in cc["income"].keys() | fc["income"].keys()
                    },
                },
            }
            assert (
                sum(v for k, v in contrast["town_first_path"].items() if k != "diagonal_sum")
                == contrast["town_first_path"]["diagonal_sum"]
            )
            output["paired_seat_decompositions"][f"{seed}-{seat}"] = contrast
            seed_rows.append(contrast)
        output["seed_decompositions"][str(seed)] = {
            "both_seats_accepted": all(row["town_first_path_accepted"] for row in seed_rows),
            "descriptive_town_first_path_mean": {
                key: mean(row["town_first_path"][key] for row in seed_rows)
                for key in seed_rows[0]["town_first_path"]
            },
        }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(output, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print("Saved OFFLINE review", args.output)


if __name__ == "__main__":
    main()
