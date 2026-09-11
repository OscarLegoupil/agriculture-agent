"""Reconstruct the frozen melon screen through official actions and market helpers.

Run from the repository root after reproducing the named screen manifests and
their replays. This command never runs a game, samples game randomness, or tunes a
policy. The four accepted artifact hashes are explicit below. --reuse-cache
skips reconstruction only after checking manifests and every replay hash.
"""

import argparse
import contextlib
import gzip
import hashlib
import io
import json
import time
from collections import Counter
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace

import numpy as np

EXPECTED = {
    "incumbent": "64fe323936dc9494add413eb956b0294658a88efe28572332c94676c68a09325",
    "melon_race_only": "13f029db938d83caf2c5fdde2341e848ac139b957f343c3a53e683e8115815c2",
    "melon": "e56e8b7dc4d905580ea68c72e9003cff28b205fcf794885cee80a9dce85bce28",
    "melon_fertilizer_only": "37b7ba4423b55894cfcf1e9be0989762cf902e23d75152e2d691b589858b6a87",
}
PARITY_STEPS = (0, 143, 162, 168, 192, 239, 240, 245, 250, 255, 260, 264, 312, 600, 718)


def local_path(value):
    return Path(str(value).replace("\\", "/"))


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def analysis(row, policy, replay_root=None):
    from kaggle_environments.envs.kaggriculture import kaggriculture as game
    from kaggle_environments.utils import structify

    replay_path = local_path(row["replay_path"])
    if replay_root:
        replay_path = replay_root / replay_path.name
    raw = replay_path.read_bytes()
    replay = json.loads(raw)
    seat = row["seat"]
    cfg = replay["configuration"]
    env = SimpleNamespace(configuration=structify(cfg))
    result = {
        "name": row["name"],
        "opponent": Path(row["opponent"]).parent.name,
        "seed": row["seed"],
        "seat": seat,
        "replay_sha256": sha(raw),
        "cash": row["cash"],
        "opponent_cash": row["opponent_cash"],
        "ledger": row["ledger"],
        "losses": row["losses"],
        "realized_actions": row["realized_actions"],
        "runtime_max_seconds": row["runtime_max_seconds"],
        "runtime_p99_seconds": row["runtime_p99_seconds"],
        "statuses": row["statuses"],
        "stderr_turns": row.get("stderr_turns", 0),
        "events": [],
        "opponent_events": [],
        "daily": [],
        "game_hashes": [],
        "actions_hashes": [],
        "maturity": [],
        "verified_market_balances": 0,
        "replay_path": str(replay_path),
        "parity": {"tested": 0, "max_seconds": 0, "stderr": []},
    }
    for step in PARITY_STEPS:
        before = replay["steps"][step]
        observation = deepcopy(before[seat]["observation"])
        for key in ("step", "day", "hour", "farms", "market", "town"):
            observation[key] = deepcopy(before[0]["observation"][key])
        stderr = io.StringIO()
        started = time.perf_counter()
        with contextlib.redirect_stderr(stderr):
            predicted = policy(observation, cfg)
        result["parity"]["max_seconds"] = max(
            result["parity"]["max_seconds"], time.perf_counter() - started
        )
        assert predicted == replay["steps"][step + 1][seat]["action"], (replay_path, step)
        result["parity"]["tested"] += 1
        if stderr.getvalue():
            result["parity"]["stderr"].append(stderr.getvalue())
    commits = []
    farms_by_id = {}
    original_commit = game._commit_unit

    def commit(op, item, price, farm, private, *rest):
        success = original_commit(op, item, price, farm, private, *rest)
        if success:
            commits.append([farms_by_id[id(farm)], op, item, price])
        return success

    game._commit_unit = commit
    try:
        for index, recorded in enumerate(replay["steps"][1:], 1):
            previous = replay["steps"][index - 1]
            shared = previous[0]["observation"]
            day, hour = shared["day"], shared["hour"]
            farm = shared["farms"][seat]
            private = previous[seat]["observation"]["private"]
            action = recorded[seat].get("action") or {}
            actions = [action.get("farmer", ["PASS"]), *action.get("hands", [])]
            units = [farm["farmer"], *farm["hands"]]
            # Hash only game state, never execution durations or remaining overage.
            if day <= 10:
                state_key = [shared[k] for k in ("farms", "market", "town", "day", "hour")]
                state_key.extend(s["observation"]["private"] for s in previous)
                result["game_hashes"].append(sha(json.dumps(state_key, sort_keys=True).encode()))
                result["actions_hashes"].append(
                    sha(json.dumps([s.get("action") for s in recorded], sort_keys=True).encode())
                )
            if hour == 0:
                result["daily"].append(
                    {
                        "day": day,
                        "cash": farm["money"],
                        "shops": shared["town"]["unlocked_shops"],
                        "composition": dict(
                            Counter(
                                t.get("crop", t.get("animal", t["kind"]))
                                for row_ in farm["tiles"]
                                for t in row_
                                if isinstance(t, dict)
                            )
                        ),
                        "carried_melon": sum(inv.get("MELON", 0) for inv in private["inventories"]),
                        "shed_melon": private["shed"].get("MELON", 0),
                    }
                )
                if day == 10:
                    result["maturity"] = [
                        {"x": x, "y": y, **tile}
                        for y, row_ in enumerate(farm["tiles"])
                        for x, tile in enumerate(row_)
                        if isinstance(tile, dict) and tile.get("crop") == "MELON"
                    ]
            relevant = any(
                order[:2] == ["SELL", "MELON"]
                for player in (0, 1)
                for order in (recorded[player].get("action") or {}).get("market", [])
            )
            relevant |= 6 <= day <= 9 and any(
                o[:2] == ["BUY_PRODUCT", "FERTILIZER"] for o in action.get("market", [])
            )
            for worker, task in enumerate(actions[: len(units)]):
                x, y = units[worker]
                tile = farm["tiles"][y][x]
                relevant |= (
                    task[0] in ("HARVEST", "FERTILIZE")
                    and isinstance(tile, dict)
                    and tile.get("crop") == "MELON"
                )
                relevant |= task[0] == "DROP" and private["inventories"][worker].get("MELON", 0) > 0
            if not relevant:
                continue
            state = structify(deepcopy(previous))
            obs = state[0].observation
            farms_by_id = {id(f): i for i, f in enumerate(obs.farms)}
            for player in (0, 1):
                state[player].action = recorded[player].get("action") or {}
                f, p = obs.farms[player], state[player].observation.private
                player_action = state[player].action
                tasks = [player_action.get("farmer", ["PASS"]), *player_action.get("hands", [])]
                demand = Counter(t[1] for t in tasks if len(t) > 1 and t[0] == "PLANT")
                blocked = {crop for crop, n in demand.items() if n > p["seeds"].get(crop, 0)}
                for worker, task in enumerate(tasks):
                    if task and task[0] == "PLANT" and task[1] in blocked:
                        task = ["PASS"]
                    pos = game._farmer_position(f, worker)
                    tile = deepcopy(f["tiles"][pos[1]][pos[0]]) if pos else None
                    inv = (
                        Counter(p["inventories"][worker])
                        if worker < len(p["inventories"])
                        else Counter()
                    )
                    shed = Counter(p["shed"])
                    game._apply_unit_action(
                        f,
                        p,
                        worker,
                        task,
                        cfg["boardSize"],
                        day,
                        cfg["turnsPerDay"],
                        cfg["shedCapacity"],
                    )
                    if player != seat:
                        continue
                    after_inv = (
                        Counter(p["inventories"][worker])
                        if worker < len(p["inventories"])
                        else Counter()
                    )
                    if task[0] == "HARVEST" and after_inv["MELON"] > inv["MELON"]:
                        result["events"].append(
                            {
                                "day": day,
                                "hour": hour,
                                "op": "HARVEST",
                                "item": "MELON",
                                "qty": after_inv["MELON"] - inv["MELON"],
                                "worker": worker,
                                "position": pos,
                                "planted_day": tile["planted_day"],
                            }
                        )
                    elif task[0] == "DROP" and p["shed"].get("MELON", 0) > shed["MELON"]:
                        result["events"].append(
                            {
                                "day": day,
                                "hour": hour,
                                "op": "DROP",
                                "item": "MELON",
                                "qty": p["shed"]["MELON"] - shed["MELON"],
                                "worker": worker,
                            }
                        )
                    elif (
                        task[0] == "FERTILIZE"
                        and isinstance(tile, dict)
                        and tile.get("crop") == "MELON"
                        and after_inv["FERTILIZER"] < inv["FERTILIZER"]
                    ):
                        result["events"].append(
                            {
                                "day": day,
                                "hour": hour,
                                "op": "FERTILIZE",
                                "item": "MELON",
                                "qty": inv["FERTILIZER"] - after_inv["FERTILIZER"],
                                "worker": worker,
                                "position": pos,
                                "planted_day": tile["planted_day"],
                            }
                        )
            commits.clear()
            game._process_market(state, env)
            for player in (0, 1):
                assert (
                    obs.farms[player]["money"]
                    == recorded[0]["observation"]["farms"][player]["money"]
                ), (replay_path, index, player)
            result["verified_market_balances"] += 2
            aggregate = Counter()
            for player, op, item, price in commits:
                aggregate[(player, op, item, "qty")] += 1
                aggregate[(player, op, item, "cash")] += price
            for player, op, item in sorted(
                {(player, op, item) for player, op, item, _ in aggregate}
            ):
                if item == "MELON" or (item == "FERTILIZER" and op == "BUY_PRODUCT"):
                    destination = "events" if player == seat else "opponent_events"
                    result[destination].append(
                        {
                            "day": day,
                            "hour": hour,
                            "op": op,
                            "item": item,
                            "qty": aggregate[(player, op, item, "qty")],
                            "cash": aggregate[(player, op, item, "cash")],
                        }
                    )
    finally:
        game._commit_unit = original_commit
    return result


def summarize(data, screen_manifest, frontier_path, frontier, bootstrap_replicates, bootstrap_seed):
    """Build paired estimates; all selection remains explicitly exploratory."""
    episodes = data["episodes"]
    index = {(e["name"], e["opponent"], e["seed"], e["seat"]): e for e in episodes}
    names = ["incumbent", "melon_race_only", "melon", "melon_fertilizer_only"]
    opponents = ["reference-cok", "reference-seyam"]
    seeds = sorted({e["seed"] for e in episodes})
    resamples = np.random.default_rng(bootstrap_seed).integers(
        0, len(seeds), size=(bootstrap_replicates, len(seeds))
    )

    def mean(values):
        return float(np.mean(list(values)))

    def interval(rows, fn):
        clustered = np.array([mean(fn(e) for e in rows if e["seed"] == seed) for seed in seeds])
        lo, hi = np.quantile(clustered[resamples].mean(axis=1), [0.025, 0.975])
        return {"mean": float(clustered.mean()), "ci95": [float(lo), float(hi)]}

    def score(e):
        return float(e["cash"] > e["opponent_cash"]) + 0.5 * (e["cash"] == e["opponent_cash"])

    def base(e):
        return index["incumbent", e["opponent"], e["seed"], e["seat"]]

    def selected(e, op, day=None, item="MELON"):
        return [
            v
            for v in e["events"]
            if v["op"] == op and v["item"] == item and (day is None or v["day"] == day)
        ]

    def amount(e, op, key="qty", day=None, item="MELON"):
        return sum(v[key] for v in selected(e, op, day, item))

    def first(e, op):
        return min(v["day"] * 24 + v["hour"] for v in selected(e, op))

    def daily(e, day):
        return next(d for d in e["daily"] if d["day"] == day)

    def diagnostics(rows):
        result = {}
        for op in ("HARVEST", "DROP", "SELL"):
            hours = [first(e, op) - 240 for e in rows]
            result[op.lower()] = {
                "first_hour_mean": mean(hours),
                "first_hour_range": [min(hours), max(hours)],
                "day10_quantity_mean": mean(amount(e, op, day=10) for e in rows),
                "season_quantity_mean": mean(amount(e, op) for e in rows),
            }
        result.update(
            {
                "day10_melon_revenue": mean(amount(e, "SELL", "cash", day=10) for e in rows),
                "season_melon_revenue": mean(amount(e, "SELL", "cash") for e in rows),
                "day10_start_cash": mean(daily(e, 10)["cash"] for e in rows),
                "day11_start_cash": mean(daily(e, 11)["cash"] for e in rows),
                "day11_shed_melons": mean(daily(e, 11)["shed_melon"] for e in rows),
                "day10_opening_melons_at_yield_cap": mean(
                    sum(t["planted_day"] == 0 and t["yield_units"] == 6 for t in e["maturity"])
                    for e in rows
                ),
                "fertilizer_applications_to_melon": mean(amount(e, "FERTILIZE") for e in rows),
                "day6_to_9_fertilizer_purchase_cash": mean(
                    sum(
                        v["cash"]
                        for v in selected(e, "BUY_PRODUCT", item="FERTILIZER")
                        if 6 <= v["day"] <= 9
                    )
                    for e in rows
                ),
                "day10_composition": {
                    item: mean(daily(e, 10)["composition"].get(item, 0) for e in rows)
                    for item in ("MELON", "WHEAT", "STRAWBERRY", "COW", "SHEEP", "GOOSE")
                },
                "mean_ledger": {
                    key: mean(e["ledger"].get(key, 0) for e in rows)
                    for key in sorted(set().union(*(e["ledger"] for e in rows)))
                },
                "mean_realized_actions": {
                    key: mean(e["realized_actions"].get(key, 0) for e in rows)
                    for key in sorted(set().union(*(e["realized_actions"] for e in rows)))
                },
                "loss_totals": {
                    key: sum(e["losses"].get(key, 0) for e in rows)
                    for key in sorted(set().union(*(e["losses"] for e in rows)))
                },
            }
        )
        return result

    results = {
        "date": "2026-09-11",
        "protocol": {
            "role": "Exploratory mechanism audit of a completed development screen; not fresh confirmation or promotion evidence.",
            "seeds": seeds,
            "seats": [0, 1],
            "opponent_weights": {o: 0.5 for o in opponents},
            "draw_score": 0.5,
            "bootstrap_replicates": bootstrap_replicates,
            "bootstrap_rng_seed": bootstrap_seed,
            "bootstrap_unit": "One seed, carrying both seats, both opponent matchups, and all candidate/incumbent paired outcomes together.",
            "independence_limitation": "COK and Seyam share replay-route ancestry. Seed intervals do not quantify opponent coverage or repeated candidate-selection uncertainty.",
        },
        "sources": data["sources"],
        "opponents": json.loads(Path("reports/challenge-reference-manifest.json").read_text())[
            "references"
        ],
        "environment": {
            "package": "kaggle-environments==1.32.7",
            "interpreter_sha256": screen_manifest["interpreter_sha256"],
            "lock_sha256": screen_manifest["lock_sha256"],
            "dependencies": screen_manifest["dependencies"],
            "effective_configuration": screen_manifest["episodes"][0]["configuration"],
            "seed_note": "The interpreter removes seed from configuration and retains the resolved seed in episode info; every resolved_seed matches the declared seed.",
        },
        "audit": {
            "replays": len(episodes),
            "reconstructed_bilateral_market_balances": sum(
                e["verified_market_balances"] for e in episodes
            ),
            "reconstructed_melon_sales_reconcile_to_telemetry": all(
                amount(e, "SELL", "cash") == e["ledger"]["income:MELON"]
                and amount(e, "SELL") == e["ledger"]["units:SELL:MELON"]
                for e in episodes
            ),
            "entrypoint_and_snapshot_hash_checks": "Passed for every candidate.",
            "action_parity": {
                "tested": sum(e["parity"]["tested"] for e in episodes),
                "mismatches": [],
                "stderr": [s for e in episodes for s in e["parity"]["stderr"]],
                "max_seconds": max(e["parity"]["max_seconds"] for e in episodes),
                "method": "Frozen raw-source official loader; recorded observation only; no simulator step or future state read by callable.",
            },
            "raw_diagnosis_sha256": sha(json.dumps(data, sort_keys=True).encode()),
            "method": "Read saved states, replay only recorded unit actions and market orders on independent copies using official helpers, check resulting cash against next saved state; no daily refresh, new randomness, counterfactual game, or policy tuning.",
            "state_hash_exclusions": ["remainingOverageTime", "runtime logs"],
            "historical_harness_diff": "Baseline to screen changes add source/bundle metadata, loader checking, and overwrite protection; episode execution and Telemetry are unchanged.",
        },
        "aggregate": {},
        "mechanism": {},
        "paired_cases": [],
        "representative_timelines": [],
    }
    assert results["audit"]["reconstructed_melon_sales_reconcile_to_telemetry"]

    for name in names:
        rows = [e for e in episodes if e["name"] == name]
        results["mechanism"][name] = diagnostics(rows)
        results["aggregate"][name] = {}
        for opponent in [*opponents, "weighted"]:
            group = [e for e in rows if opponent == "weighted" or e["opponent"] == opponent]
            differences = [e["cash"] - e["opponent_cash"] for e in group]
            summary = {
                "games": len(group),
                "wins": sum(score(e) == 1 for e in group),
                "draws": sum(score(e) == 0.5 for e in group),
                "score": interval(group, score),
                "cash": interval(group, lambda e: e["cash"]),
                "gap": interval(group, lambda e: e["cash"] - e["opponent_cash"]),
                "gap_median": float(np.median(differences)),
                "gap_p10": float(np.quantile(differences, 0.1)),
                "paired_score_change": interval(group, lambda e: score(e) - score(base(e))),
                "paired_own_cash_change": interval(group, lambda e: e["cash"] - base(e)["cash"]),
                "paired_opponent_cash_change": interval(
                    group, lambda e: e["opponent_cash"] - base(e)["opponent_cash"]
                ),
                "paired_gap_change": interval(
                    group,
                    lambda e: (
                        (e["cash"] - e["opponent_cash"])
                        - (base(e)["cash"] - base(e)["opponent_cash"])
                    ),
                ),
                "non_done_games": sum(e["statuses"] != ["DONE", "DONE"] for e in group),
                "stderr_turns": sum(e["stderr_turns"] for e in group),
                "max_runtime_seconds": max(e["runtime_max_seconds"] for e in group),
                "max_episode_p99_runtime_seconds": max(e["runtime_p99_seconds"] for e in group),
            }
            results["aggregate"][name][opponent] = summary
        if name == "incumbent":
            continue
        for e in rows:
            b = base(e)
            case = {
                "candidate": name,
                "opponent": e["opponent"],
                "seed": e["seed"],
                "seat": e["seat"],
                "candidate_replay_sha256": e["replay_sha256"],
                "incumbent_replay_sha256": b["replay_sha256"],
                "first_action_divergence_step": next(
                    (
                        i
                        for i, (x, y) in enumerate(
                            zip(e["actions_hashes"], b["actions_hashes"], strict=True)
                        )
                        if x != y
                    ),
                    None,
                ),
                "first_state_divergence_step": next(
                    (
                        i
                        for i, (x, y) in enumerate(
                            zip(e["game_hashes"], b["game_hashes"], strict=True)
                        )
                        if x != y
                    ),
                    None,
                ),
                "first_shop_divergence_day": next(
                    (
                        x["day"]
                        for x, y in zip(e["daily"], b["daily"], strict=True)
                        if x["shops"] != y["shops"]
                    ),
                    None,
                ),
                "first_harvest_hour": [first(b, "HARVEST") - 240, first(e, "HARVEST") - 240],
                "first_sale_hour": [first(b, "SELL") - 240, first(e, "SELL") - 240],
                "day10_melon_revenue_change": amount(e, "SELL", "cash", 10)
                - amount(b, "SELL", "cash", 10),
                "season_melon_revenue_change": amount(e, "SELL", "cash")
                - amount(b, "SELL", "cash"),
                "own_cash_change": e["cash"] - b["cash"],
                "opponent_cash_change": e["opponent_cash"] - b["opponent_cash"],
                "score_change": score(e) - score(b),
            }
            results["paired_cases"].append(case)
    for e in episodes:
        if e["opponent"] == "reference-cok" and e["seed"] == 5000 and e["seat"] == 0:
            results["representative_timelines"].append(
                {
                    "candidate": e["name"],
                    "opponent": e["opponent"],
                    "seed": e["seed"],
                    "seat": e["seat"],
                    "day10": [v for v in e["events"] if v["day"] == 10],
                }
            )

    opponent_records = [
        {
            "name": e["name"],
            "opponent": e["opponent"],
            "seed": e["seed"],
            "candidate_seat": e["seat"],
            "events": e["opponent_events"],
        }
        for e in episodes
        if e["name"] in ("incumbent", "melon_race_only")
    ]
    opponent_index = {
        (e["name"], e["opponent"], e["seed"], e["candidate_seat"]): e for e in opponent_records
    }
    results["audit"]["opponent_sales_method"] = (
        "Both players' transactions are reconstructed in the same official market pass."
    )
    results["market_transfer"] = {}
    for opponent in [*opponents, "weighted"]:
        rows = [
            e
            for e in episodes
            if e["name"] == "melon_race_only"
            and (opponent == "weighted" or e["opponent"] == opponent)
        ]
        own_gain = mean(amount(e, "SELL", "cash") - amount(base(e), "SELL", "cash") for e in rows)
        opponent_gain = mean(
            amount(opponent_index[e["name"], e["opponent"], e["seed"], e["seat"]], "SELL", "cash")
            - amount(
                opponent_index["incumbent", e["opponent"], e["seed"], e["seat"]], "SELL", "cash"
            )
            for e in rows
        )
        margin_gain = results["aggregate"]["melon_race_only"][opponent]["paired_gap_change"]["mean"]
        results["market_transfer"][opponent] = {
            "own_melon_revenue_change": own_gain,
            "opponent_melon_revenue_change": opponent_gain,
            "melon_cash_margin_change": own_gain - opponent_gain,
            "combined_bilateral_melon_revenue_change": own_gain + opponent_gain,
            "final_cash_margin_change": margin_gain,
            "melon_share_of_cash_margin_change": (own_gain - opponent_gain) / margin_gain,
            "remainder_margin_change": margin_gain - own_gain + opponent_gain,
            "qualification": "Accounting identity, not a controlled causal decomposition; later shops and other production can respond to the intervention.",
        }
    for case in results["paired_cases"]:
        if case["candidate"] == "melon_race_only":
            key = case["opponent"], case["seed"], case["seat"]
            case["opponent_melon_revenue_change"] = amount(
                opponent_index[("melon_race_only", *key)], "SELL", "cash"
            ) - amount(opponent_index[("incumbent", *key)], "SELL", "cash")
            case["melon_cash_margin_change"] = (
                case["season_melon_revenue_change"] - case["opponent_melon_revenue_change"]
            )

    results["current_frontier"] = {
        "manifest": str(frontier_path),
        "manifest_sha256": sha(frontier_path.read_bytes()),
        "revision": frontier["revision"],
        "declared_panel": frontier["declared_panel"],
        "opponent_executables": frontier["executable_bundles"],
        "results": {},
        "conclusion": "Historical-pool challenger only: no demonstrated improvement against the current Mooman reference; both policies lose every inspected game.",
    }
    for candidate in ("incumbent", "melon_race_only"):
        rows = [
            e
            for e in frontier["episodes"]
            if frontier["candidates"][e["candidate"]]["name"] == candidate
        ]
        results["current_frontier"]["results"][candidate] = {
            "games": len(rows),
            "wins": sum(score(e) == 1 for e in rows),
            "draws": sum(score(e) == 0.5 for e in rows),
            "cash": mean(e["cash"] for e in rows),
            "gap": mean(e["cash"] - e["opponent_cash"] for e in rows),
            "non_done_games": sum(e["statuses"] != ["DONE", "DONE"] for e in rows),
            "stderr_turns": sum(e.get("stderr_turns", 0) for e in rows),
        }
    return results


def load_panels(incumbent_path, screen_path):
    from kaggle_environments.agent import get_last_callable
    from kaggle_environments.envs.kaggriculture import kaggriculture as game

    manifests = [json.loads(p.read_text()) for p in (incumbent_path, screen_path)]
    for key in ("environment_version", "interpreter_sha256", "lock_sha256", "dependencies"):
        assert manifests[0][key] == manifests[1][key], key
    sources, policies, rows = {}, {}, []
    configuration = manifests[0]["episodes"][0]["configuration"]
    for manifest_path, manifest in zip((incumbent_path, screen_path), manifests, strict=True):
        assert manifest["complete"]
        for opponent in manifest["declared_panel"]["opponents"]:
            assert sha(local_path(opponent).read_bytes()) == manifest["hashes"][opponent]
        for path, metadata in manifest["candidates"].items():
            name = metadata["name"]
            if name not in EXPECTED:
                continue
            assert name not in sources, name
            content = local_path(path).read_bytes()
            assert sha(content) == metadata["sha256"] == EXPECTED[name], name
            assert gzip.decompress(local_path(metadata["snapshot"]).read_bytes()) == content
            namespace = {}
            exec(content.decode(), namespace)
            selected = get_last_callable(content.decode())
            assert selected.__code__ == namespace["agent"].__code__, name
            sources[name] = {
                **metadata,
                "entrypoint_verified": True,
                "manifest": str(manifest_path),
                "manifest_sha256": sha(manifest_path.read_bytes()),
            }
            policies[name] = selected
        for row in manifest["episodes"]:
            name = manifest["candidates"][row["candidate"]]["name"]
            if name in EXPECTED:
                assert row["seed"] == row["resolved_seed"]
                assert row["configuration"] == configuration
                rows.append({**row, "name": name})
    assert sources.keys() == EXPECTED.keys()
    keys = {(r["name"], r["opponent"], r["seed"], r["seat"]) for r in rows}
    assert len(keys) == len(rows)
    cases = {(r["opponent"], r["seed"], r["seat"]) for r in rows}
    assert keys == {(name, *case) for name in EXPECTED for case in cases}
    assert sha(Path(game.__file__).read_bytes()) == manifests[0]["interpreter_sha256"]
    return manifests[1], sources, policies, rows


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--incumbent-manifest", type=Path, default=Path("data/raw/breakthrough-season-screen.json")
    )
    parser.add_argument(
        "--screen-manifest", type=Path, default=Path("data/raw/breakthrough-melon-screen.json")
    )
    parser.add_argument(
        "--frontier-manifest", type=Path, default=Path("data/raw/breakthrough-race-mooman.json")
    )
    parser.add_argument(
        "--replays", type=Path, help="Override saved replay directory; filenames remain unchanged."
    )
    parser.add_argument("--cache", type=Path, default=Path("data/interim/melon-diagnosis.json"))
    parser.add_argument(
        "--reuse-cache",
        action="store_true",
        help="Reuse completed accounting after verifying source, manifest, and replay identities.",
    )
    parser.add_argument(
        "--output", type=Path, default=Path("reports/results/breakthrough-melon-diagnosis.json")
    )
    parser.add_argument("--bootstrap-replicates", type=int, default=20000)
    parser.add_argument("--bootstrap-seed", type=int, default=1729)
    args = parser.parse_args()
    assert args.bootstrap_replicates > 0
    screen, sources, policies, rows = load_panels(args.incumbent_manifest, args.screen_manifest)
    frontier = json.loads(args.frontier_manifest.read_text())
    assert frontier["complete"]
    for key in ("environment_version", "interpreter_sha256", "lock_sha256", "dependencies"):
        assert frontier[key] == screen[key], key
    for metadata in frontier["candidates"].values():
        assert metadata["sha256"] == EXPECTED[metadata["name"]]
    for row in frontier["episodes"]:
        assert row["seed"] == row["resolved_seed"]
        assert row["configuration"] == screen["episodes"][0]["configuration"]
    for bundle in frontier["executable_bundles"].values():
        for path, expected in bundle.items():
            assert sha(local_path(path).read_bytes()) == expected, path
    if args.reuse_cache:
        data = json.loads(args.cache.read_text())
        assert data["complete"] and data["sources"] == sources
        assert data["analysis_source_sha256"] == sha(Path(__file__).read_bytes())
        assert len(data["episodes"]) == len(rows)
        for episode in data["episodes"]:
            path = local_path(episode["replay_path"])
            if args.replays:
                path = args.replays / path.name
            assert sha(path.read_bytes()) == episode["replay_sha256"], path
    else:
        data = {
            "sources": sources,
            "episodes": [],
            "complete": False,
            "analysis_source_sha256": sha(Path(__file__).read_bytes()),
        }
        args.cache.parent.mkdir(parents=True, exist_ok=True)
        for row in rows:
            data["episodes"].append(analysis(row, policies[row["name"]], args.replays))
            print(
                len(data["episodes"]),
                row["name"],
                row["opponent"],
                row["seed"],
                row["seat"],
                flush=True,
            )
        data["complete"] = True
        args.cache.write_text(json.dumps(data, indent=2) + "\n")
    result = summarize(
        data,
        screen,
        args.frontier_manifest,
        frontier,
        args.bootstrap_replicates,
        args.bootstrap_seed,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n")
    print(args.output, flush=True)


if __name__ == "__main__":
    main()
