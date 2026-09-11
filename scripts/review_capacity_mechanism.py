"""Audit capacity screens from recorded states; run no new games."""

import argparse
import contextlib
import gzip
import hashlib
import io
import json
from collections import Counter
from pathlib import Path
from statistics import mean, median

import numpy as np
from phase3_field_economics import analyze

DIGESTS = {
    "v8": "64fe323936dc9494add413eb956b0294658a88efe28572332c94676c68a09325",
    "fleet": "9400f9b0cdaa02d268ab9e234779d17013f2facf5f5517698bdfdb04671464b7",
    "cereal": "c2b3162de26b82cb6057e94cb121b5655b7ee5c2e30659520f379f6ac7828b05",
}
PANELS = {
    "mooman": {
        "v8": "data/raw/breakthrough-race-mooman.json",
        "fleet": "data/raw/breakthrough-fleet-mooman.json",
        "cereal": "data/raw/breakthrough-cereal-mooman.json",
    },
    "anchor": {
        "v8": "data/raw/breakthrough-season-screen.json",
        "fleet": "data/raw/breakthrough-fleet-corrected.json",
        "cereal": "data/raw/breakthrough-fleet-capacity.json",
    },
}


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


class SavedReplay:
    """Read original JSON bytes whether their storage is compressed or plain."""

    def __init__(self, value):
        self.path = Path(str(value).replace("\\", "/"))
        if not self.path.exists():
            self.path = self.path.with_suffix(self.path.suffix + ".gz")

    def read_bytes(self):
        raw = self.path.read_bytes()
        return gzip.decompress(raw) if self.path.suffix == ".gz" else raw

    def __str__(self):
        return str(self.path)


def key(row):
    return row["opponent"], row["seed"], row["seat"]


def score(row):
    return float(row["cash"] > row["opponent_cash"]) + 0.5 * (row["cash"] == row["opponent_cash"])


def gap(row):
    return row["cash"] - row["opponent_cash"]


def aggregate(rows):
    values = [gap(row) for row in rows]
    return {
        "games": len(rows),
        "wins": sum(score(row) == 1 for row in rows),
        "draws": sum(score(row) == 0.5 for row in rows),
        "score": mean(map(score, rows)),
        "mean_cash": mean(row["cash"] for row in rows),
        "mean_gap": mean(values),
        "median_gap": median(values),
        "p10_gap": float(np.quantile(values, 0.1)),
        "errors": sum(row["statuses"] != ["DONE", "DONE"] for row in rows),
        "stderr_turns": sum(row.get("stderr_turns", 0) for row in rows),
        "ledger_means": {
            name: mean(row["ledger"].get(name, 0) for row in rows)
            for name in sorted(set().union(*(row["ledger"] for row in rows)))
        },
    }


def first_shop_difference(left, right):
    for before, after in zip(left["daily"], right["daily"], strict=True):
        if before["shops"] != after["shops"]:
            return before["step"] // 24
    return None


def load_panels():
    result, inputs = {}, {}
    environment = set()
    opponents = {}
    for pool, agents in PANELS.items():
        result[pool] = {}
        for agent, filename in agents.items():
            path = Path(filename)
            raw = path.read_bytes()
            manifest = json.loads(raw)
            assert manifest["complete"]
            inputs[filename] = sha(raw)
            environment.add(manifest["interpreter_sha256"])
            rows = [
                row
                for row in manifest["episodes"]
                if manifest["candidates"][row["candidate"]]["sha256"] == DIGESTS[agent]
            ]
            result[pool][agent] = {key(row): row for row in rows}
            assert len(result[pool][agent]) == len(rows), (pool, agent, "duplicate scenario")
            for row in rows:
                expected = opponents.setdefault(
                    row["opponent"], manifest["hashes"][row["opponent"]]
                )
                assert manifest["hashes"][row["opponent"]] == expected
        assert set(result[pool]["v8"]) == set(result[pool]["fleet"]) == set(result[pool]["cereal"])
        for scenario, cereal in result[pool]["cereal"].items():
            for agent in ("v8", "fleet"):
                assert cereal["configuration"] == result[pool][agent][scenario]["configuration"]
    assert len(environment) == 1
    return result, inputs, next(iter(environment)), opponents


def pool_summary(agents):
    results = {name: aggregate(list(rows.values())) for name, rows in agents.items()}
    scenarios = sorted(agents["cereal"])
    seed_rows = []
    for seed in sorted({scenario[1] for scenario in scenarios}):
        same = [scenario for scenario in scenarios if scenario[1] == seed]
        entry = {"seed": seed}
        for agent, rows in agents.items():
            entry[agent] = aggregate([rows[scenario] for scenario in same])
            entry[agent].pop("ledger_means")
        entry["paired_gap_gain_vs_fleet"] = mean(
            gap(agents["cereal"][scenario]) - gap(agents["fleet"][scenario]) for scenario in same
        )
        entry["paired_gap_gain_vs_v8"] = mean(
            gap(agents["cereal"][scenario]) - gap(agents["v8"][scenario]) for scenario in same
        )
        seed_rows.append(entry)
    net = sum(row["paired_gap_gain_vs_fleet"] for row in seed_rows)
    concentration = sorted(seed_rows, key=lambda row: -row["paired_gap_gain_vs_fleet"])
    return {
        "agents": results,
        "by_seed": seed_rows,
        "largest_seed": concentration[0]["seed"],
        "largest_seed_share_of_net_gap_gain": concentration[0]["paired_gap_gain_vs_fleet"] / net,
        "top_three_seeds_share_of_net_gap_gain": sum(
            row["paired_gap_gain_vs_fleet"] for row in concentration[:3]
        )
        / net,
        "excluding_5000": {
            name: aggregate([row for scenario, row in rows.items() if scenario[1] != 5000])
            for name, rows in agents.items()
        },
        "shop_first_difference_cereal_vs_fleet": dict(
            Counter(
                str(first_shop_difference(agents["fleet"][scenario], agents["cereal"][scenario]))
                for scenario in scenarios
            )
        ),
        "scenarios": [
            {
                "opponent": scenario[0],
                "seed": scenario[1],
                "seat": scenario[2],
                "first_shop_difference_day": first_shop_difference(
                    agents["fleet"][scenario], agents["cereal"][scenario]
                ),
                "shops": {
                    name: rows[scenario]["daily"][-1]["shops"] for name, rows in agents.items()
                },
            }
            for scenario in scenarios
        ],
    }


def first_divergence(left, right, seat):
    first_action = first_production = None
    for index, (before, after) in enumerate(zip(left["steps"], right["steps"], strict=True)):
        if index and before[seat]["action"] != after[seat]["action"] and first_action is None:
            first_action = {
                "step": index - 1,
                "day": (index - 1) // 24,
                "hour": (index - 1) % 24,
                "fleet_action": before[seat]["action"],
                "cereal_action": after[seat]["action"],
                "cash_before": left["steps"][index - 1][0]["observation"]["farms"][seat]["money"],
            }
        lf = before[0]["observation"]["farms"][seat]
        rf = after[0]["observation"]["farms"][seat]
        if first_production is None:
            changes = []
            for y, (lrow, rrow) in enumerate(zip(lf["tiles"], rf["tiles"], strict=True)):
                for x, (lt, rt) in enumerate(zip(lrow, rrow, strict=True)):
                    lc = lt.get("crop", lt.get("animal")) if isinstance(lt, dict) else None
                    rc = rt.get("crop", rt.get("animal")) if isinstance(rt, dict) else None
                    if lc != rc:
                        changes.append({"tile": [x, y], "fleet": lc, "cereal": rc})
            if changes:
                first_production = {"observed_step": index, "changes": changes}
        if first_action and first_production:
            break
    return {"first_action": first_action, "first_production": first_production}


def recorded_budget_diagnostic(agents):
    """Isolate the optional route budget on one existing opening observation."""
    scenario = ("data/raw/reference-seyam/main.py", 5006, 0)
    rows = {name: agents[name][scenario] for name in ("fleet", "cereal")}
    replay = json.loads(SavedReplay(rows["fleet"]["replay_path"]).read_bytes())
    cases = {}
    for agent, digest in DIGESTS.items():
        if agent == "v8":
            continue
        source = gzip.decompress(Path("reports/sources", digest + ".py.gz").read_bytes())
        assert sha(source) == digest
        source = source.decode()
        original = "deadline = time.perf_counter() + 0.065"
        assert source.count(original) == 1
        for mode, budget in (("ample_route_budget", "5.0"), ("zero_route_budget", "0.0")):
            changed = source.replace(original, "deadline = time.perf_counter() + " + budget)
            scope = {"__name__": "recorded_budget_diagnostic"}
            exec(compile(changed, "frozen-" + digest + ".py", "exec"), scope)
            stderr = io.StringIO()
            with contextlib.redirect_stderr(stderr):
                scope["agent"](replay["steps"][0][0]["observation"], replay["configuration"])
                action = scope["agent"](
                    replay["steps"][1][0]["observation"], replay["configuration"]
                )
            cases[agent + "-" + mode] = {"action": action, "stderr": stderr.getvalue()}
    assert cases["fleet-zero_route_budget"]["action"] == replay["steps"][2][0]["action"]
    assert (
        cases["fleet-ample_route_budget"]["action"] == cases["cereal-ample_route_budget"]["action"]
    )
    return {
        "scope": "Offline diagnostic only. Two frozen policies, each with ample or zero optional route time, called on the same two recorded opening observations. No new game or competitive score.",
        "scenario": {"opponent": scenario[0], "seed": scenario[1], "seat": scenario[2], "step": 1},
        "recorded_stderr_messages": {name: row["stderr_messages"] for name, row in rows.items()},
        "cases": cases,
        "interpretation": "The recorded fleet opening action is reproduced by zero route time. Both policies agree with ample time. The early shop divergence in this pair is consistent with the observed fleet budget fallbacks, not solely a crop-cap intervention.",
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--cache", type=Path, default=Path("data/interim/capacity-review-ledgers.json")
    )
    parser.add_argument(
        "--output", type=Path, default=Path("reports/results/breakthrough-capacity-review.json")
    )
    parser.add_argument("--reuse-cache", action="store_true")
    args = parser.parse_args()
    panels, inputs, interpreter, opponents = load_panels()
    helper_hash = sha(Path(__file__).with_name("phase3_field_economics.py").read_bytes())
    cache = (
        json.loads(args.cache.read_text())
        if args.reuse_cache
        else {"helper_sha256": helper_hash, "replays": {}}
    )
    assert cache["helper_sha256"] == helper_hash
    cases = panels["mooman"]
    expected_identifiers = {
        f"{agent}-{scenario[1]}-{scenario[2]}"
        for agent in ("fleet", "cereal")
        for scenario in cases[agent]
    }
    if args.reuse_cache:
        assert set(cache["replays"]) == expected_identifiers
    for agent in ("fleet", "cereal"):
        for scenario, row in sorted(cases[agent].items()):
            replay = SavedReplay(row["replay_path"])
            raw = replay.read_bytes()
            digest = sha(raw)
            identifier = f"{agent}-{scenario[1]}-{scenario[2]}"
            if args.reuse_cache:
                result = cache["replays"][identifier]
                assert result["sha256"] == digest
            else:
                result = analyze(replay)
            assert result["interpreter_sha256"] == interpreter
            recorded_ledger = row["ledger"]
            reconstructed = result["players"][row["seat"]]["ledger"]
            for name, value in recorded_ledger.items():
                if name.startswith(("income:", "expense:", "units:")):
                    assert reconstructed.get(name, 0) == value, (identifier, name)
            if args.reuse_cache:
                assert (result["candidate"], result["seed"], result["seat"]) == (
                    agent,
                    row["seed"],
                    row["seat"],
                )
                continue
            result.update(candidate=agent, seed=row["seed"], seat=row["seat"])
            cache["replays"][identifier] = result
            args.cache.parent.mkdir(parents=True, exist_ok=True)
            args.cache.write_text(json.dumps(cache) + "\n")
            print(identifier, "verified", flush=True)
    output = {
        "method": "Ledgers use saved states and official unit/market helpers only; every reconstructed cash balance must match the next recorded state. A separate, explicitly offline opening diagnostic invokes frozen policies with altered optional route budgets. No new complete game or future random draw is run.",
        "inputs": inputs,
        "candidate_sha256": DIGESTS,
        "source_changes_fleet_to_cereal": {
            "crop_ceiling": "50 -> count of currently unlocked observed tiles",
            "wheat_valuation_boost_threshold": "8 -> 24 planned wheat when animals exist",
            "opening_crop_rule": "Before day 15, the override switches from strawberries to wheat once 34 strawberries are planned; the seven-wheat opening floor remains.",
            "scheduler": "Identical code, including the 65 ms optional daily-route time limit.",
        },
        "opponent_sha256": opponents,
        "interpreter_sha256": interpreter,
        "helper_sha256": helper_hash,
        "analysis_sha256": sha(Path(__file__).read_bytes()),
        "pools": {name: pool_summary(agents) for name, agents in panels.items()},
        "verified_bilateral_cash_transitions": sum(
            value["verified_cash_transitions"] for value in cache["replays"].values()
        ),
        "daily_mooman_cases": {},
        "selected_divergences": {},
        "offline_budget_diagnostic": recorded_budget_diagnostic(panels["anchor"]),
        "fixed_shop_counterfactual_design": {
            "status": "designed_not_run",
            "scope": "Offline mechanism diagnosis only; exclude every result from competitive scores, selection gates and live-strength claims.",
            "initial_panel": {
                "seeds": [5000, 5001],
                "seats": [0, 1],
                "agents": ["fleet", "cereal"],
                "shop_donors": ["fleet", "cereal"],
                "games": 16,
            },
            "opponent": "The pinned reacting Mooman executable, not recorded opposing actions.",
            "intervention": "Wrap official _end_of_day: first execute the unmodified function, including actual growth, inventory transfer and weed draws; when it appends a shop, replace only that newly appended shop with the corresponding entry of the predeclared donor schedule. Do not change market prices, inventory, production, weather/weed events or future observation fields.",
            "observability": "Keep the complete donor schedule only in the offline environment wrapper. Pass unchanged observation/configuration schemas to both policies; expose each shop only at its normal unlock time.",
            "controls": "Donor-policy cells must reproduce original no-fallback witnesses before interpreting cross-donor cells. Record all fallback events. If load changes a donor trajectory, do not claim an exact town-mediated causal decomposition.",
            "readout": "For each donor schedule, compare cereal against fleet on matched seeds/seats. Separately compare donor schedules within each policy, and report the interaction. Never add these modified-environment games to anchor or challenge scores.",
        },
    }
    for identifier, replay in cache["replays"].items():
        own = replay["players"][replay["seat"]]
        rival = replay["players"][1 - replay["seat"]]
        periods = {}
        for label, start, stop in (
            ("opening_days_0_9", 0, 10),
            ("middle_days_10_19", 10, 20),
            ("terminal_days_20_29", 20, 30),
        ):
            periods[label] = {}
            for name, player in (("own", own), ("opponent", rival)):
                ledger = sum(
                    (Counter(day["ledger"]) for day in player["daily"][start:stop]), Counter()
                )
                periods[label][name] = {
                    k: v
                    for k, v in ledger.items()
                    if k.startswith(("income:", "expense:", "units:SELL:"))
                }
        output["daily_mooman_cases"][identifier] = {
            "replay_sha256": replay["sha256"],
            "periods": periods,
            "daily": [
                {
                    "day": day,
                    "own_cash": ours["cash"],
                    "opponent_cash": theirs["cash"],
                    "own_composition": ours["composition"],
                    "opponent_composition": theirs["composition"],
                    "own_new_cohorts": ours["new_cohorts"],
                    "opponent_new_cohorts": theirs["new_cohorts"],
                    "own_income": {
                        k: v for k, v in ours["ledger"].items() if k.startswith("income:")
                    },
                    "opponent_income": {
                        k: v for k, v in theirs["ledger"].items() if k.startswith("income:")
                    },
                }
                for day, (ours, theirs) in enumerate(zip(own["daily"], rival["daily"], strict=True))
            ],
        }
    for seed in (5000, 5001, 5002, 5005, 5006):
        scenario = ("data/raw/reference-mooman/main.py", seed, 0)
        left, right = (
            json.loads(SavedReplay(cases[agent][scenario]["replay_path"]).read_bytes())
            for agent in ("fleet", "cereal")
        )
        output["selected_divergences"][str(seed)] = first_divergence(left, right, 0)
    output["period_mean_changes_cereal_vs_fleet"] = {}
    for period in ("opening_days_0_9", "middle_days_10_19", "terminal_days_20_29"):
        period_result = {}
        for side in ("own", "opponent"):
            changes = []
            for seed in range(5000, 5008):
                for seat in (0, 1):
                    old = output["daily_mooman_cases"][f"fleet-{seed}-{seat}"]["periods"][period][
                        side
                    ]
                    new = output["daily_mooman_cases"][f"cereal-{seed}-{seat}"]["periods"][period][
                        side
                    ]
                    changes.append(
                        {name: new.get(name, 0) - old.get(name, 0) for name in set(old) | set(new)}
                    )
            averaged = {
                name: mean(change.get(name, 0) for change in changes)
                for name in sorted(set().union(*changes))
            }
            income = sum(value for name, value in averaged.items() if name.startswith("income:"))
            expense = sum(value for name, value in averaged.items() if name.startswith("expense:"))
            period_result[side] = {
                "ledger_mean_changes": averaged,
                "income_change": income,
                "expense_change": expense,
                "net_cash_change": income - expense,
            }
        period_result["cash_gap_change"] = (
            period_result["own"]["net_cash_change"] - period_result["opponent"]["net_cash_change"]
        )
        output["period_mean_changes_cereal_vs_fleet"][period] = period_result
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(output, separators=(",", ":")) + "\n")
    print("Saved", args.output, flush=True)


if __name__ == "__main__":
    main()
