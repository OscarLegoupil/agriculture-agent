"""Prepare or run an OFFLINE fixed-shop counterfactual, never a competitive benchmark.

The default command only prepares the predeclared sixteen cases. Add --run after
allocating game processes. Each process runs one game and preserves the official
random draws before replacing a newly unlocked shop. Policies receive ordinary
public observations and never receive the donor's future shop schedule.
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import time
from concurrent.futures import ProcessPoolExecutor
from datetime import UTC, datetime
from pathlib import Path

if __package__:
    from .benchmark import provenance, stderr_summary, verify_bundles
    from .evidence_io import read_result
    from .telemetry import Telemetry
else:
    from benchmark import provenance, stderr_summary, verify_bundles
    from evidence_io import read_result
    from telemetry import Telemetry

POLICIES = {
    "fleet": "9400f9b0cdaa02d268ab9e234779d17013f2facf5f5517698bdfdb04671464b7",
    "cereal": "c2b3162de26b82cb6057e94cb121b5655b7ee5c2e30659520f379f6ac7828b05",
}
DONORS = {
    "fleet": "data/raw/breakthrough-fleet-mooman.json",
    "cereal": "data/raw/breakthrough-cereal-mooman.json",
}
OPPONENT = "data/raw/reference-mooman/main.py"
LABEL = {
    "evidence_kind": "offline_counterfactual",
    "competitive_score_eligible": False,
    "warning": "Altered environment. Exclude from competitive scores, promotion gates, ratings and live-strength claims.",
}
SCOPE = {
    "changed": "Only the identity of each newly appended public shop, after the official _end_of_day has completed.",
    "preserved": "Official growth, animal refresh, weed RNG draws, inventory transfer, worker reset, shop RNG draw, actions, market execution and demand timing.",
    "policy_information": "Unchanged observation and configuration schemas. The future donor schedule stays in the diagnostic environment only.",
    "interpretation": "Compare policies within each donor and donors within each policy; report their interaction. Control failures or differing runtime fallbacks preclude an exact town-mediated causal decomposition.",
}


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode()


def read_bytes(filename):
    path = Path(str(filename).replace("\\", "/"))
    if not path.exists() and path.suffix != ".gz":
        path = path.with_suffix(path.suffix + ".gz")
    raw = path.read_bytes()
    return gzip.decompress(raw) if path.suffix == ".gz" else raw


class FixedShopSchedule:
    """Process-local environment intervention; never patch or supply a policy."""

    def __init__(self, env, schedule):
        from kaggle_environments.envs.kaggriculture import kaggriculture as game

        self.game, self.env = game, env
        self.schedule = tuple(schedule)
        if len(self.schedule) != game.MAX_SHOP_INSTANCES or any(
            shop not in game.SHOPS for shop in self.schedule
        ):
            raise ValueError("A complete, valid eight-shop donor schedule is required")
        self.events = []

    def __enter__(self):
        self.original = self.game._end_of_day
        self.game._end_of_day = self.refresh
        return self

    def __exit__(self, *args):
        self.game._end_of_day = self.original

    def refresh(self, state, env, day):
        if env is not self.env:
            raise RuntimeError("A fixed-shop process must contain only its designated environment")
        previous = list(state[0].observation.town.unlocked_shops)
        result = self.original(state, env, day)
        shops = state[0].observation.town.unlocked_shops
        if len(shops) == len(previous):
            return result
        if len(shops) != len(previous) + 1 or shops[:-1] != previous:
            raise RuntimeError("Official shop append contract changed")
        index = len(previous)
        actual, replacement = shops[-1], self.schedule[index]
        shops[-1] = replacement
        self.events.append(
            {
                "shop_index": index,
                "visible_step": (day + 1) * env.configuration.turnsPerDay,
                "official_draw": actual,
                "replacement": replacement,
                "changed": actual != replacement,
                "post_official_farms_sha256": digest(canonical(state[0].observation.farms)),
            }
        )
        return result


def donor_record(row):
    raw = read_bytes(row["replay_path"])
    replay = json.loads(raw)
    schedule = replay["steps"][-1][0]["observation"]["town"]["unlocked_shops"]
    if schedule != row["daily"][-1]["shops"]:
        raise ValueError("Donor replay and manifest disagree about shops")
    unlocks, previous = [], []
    for step, state in enumerate(replay["steps"]):
        shops = state[0]["observation"]["town"]["unlocked_shops"]
        if shops != previous:
            if len(shops) != len(previous) + 1 or shops[:-1] != previous:
                raise ValueError("Donor contains an unexpected town transition")
            unlocks.append(step)
            previous = shops
    interval = row["configuration"]["townShopUnlockInterval"] * row["configuration"]["turnsPerDay"]
    if unlocks != [interval * i for i in range(1, 9)]:
        raise ValueError("Donor does not have the predeclared eight normal unlocks")
    return {
        "schedule": schedule,
        "schedule_sha256": digest(canonical(schedule)),
        "unlock_steps": unlocks,
        "replay_path": row["replay_path"],
        "replay_sha256": digest(raw),
        "recorded_stderr_turns": row.get("stderr_turns", 0),
        "recorded_final_cash": [row["cash"], row["opponent_cash"]],
    }


def prepare(workdir):
    """Freeze source and donor identities without executing any policy or game."""
    manifests = {name: read_result(path) for name, path in DONORS.items()}
    frozen, selected = {}, {}
    for name, expected in POLICIES.items():
        source = read_bytes(Path("reports/sources") / (expected + ".py.gz"))
        if digest(source) != expected:
            raise ValueError(f"Frozen {name} source hash mismatch")
        target = workdir / expected / "main.py"
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists() and target.read_bytes() != source:
            raise ValueError(f"Existing diagnostic artifact differs: {target}")
        target.write_bytes(source)
        frozen[name] = str(target)
        manifest = manifests[name]
        if not manifest["complete"]:
            raise ValueError("A donor benchmark is incomplete")
        rows = [
            row
            for row in manifest["episodes"]
            if manifest["candidates"][row["candidate"]]["sha256"] == expected
            and row["opponent"].replace("\\", "/") == OPPONENT
            and row["seed"] in (5000, 5001)
        ]
        selected[name] = {(row["seed"], row["seat"]): row for row in rows}
        if len(rows) != 4 or set(selected[name]) != {(s, p) for s in (5000, 5001) for p in (0, 1)}:
            raise ValueError("Expected exactly seeds 5000/5001 in both seats for each donor")
    source_provenance = provenance([*frozen.values(), OPPONENT])
    for manifest in manifests.values():
        if manifest["interpreter_sha256"] != source_provenance["interpreter_sha256"]:
            raise ValueError("Installed official interpreter differs from the donor environment")
        recorded_bundle = next(iter(manifest["executable_bundles"].values()))
        verify_bundles({"executable_bundles": {"donor_opponent": recorded_bundle}})
    donors, cases = {}, []
    for seed, seat in sorted(selected["fleet"]):
        rows = {name: selected[name][seed, seat] for name in POLICIES}
        if rows["fleet"]["configuration"] != rows["cereal"]["configuration"]:
            raise ValueError("Donor effective configurations differ")
        for donor, row in rows.items():
            identifier = f"{donor}-{seed}-{seat}"
            donors[identifier] = donor_record(row)
        for donor in POLICIES:
            for candidate in POLICIES:
                cases.append(
                    {
                        **LABEL,
                        "case_id": f"{seed}-{seat}-{donor}-town-{candidate}",
                        "candidate": candidate,
                        "candidate_path": frozen[candidate],
                        "candidate_sha256": POLICIES[candidate],
                        "opponent": OPPONENT,
                        "seed": seed,
                        "seat": seat,
                        "donor": f"{donor}-{seed}-{seat}",
                        "is_donor_policy_control": candidate == donor,
                        "configuration": rows[donor]["configuration"],
                    }
                )
    return {
        **LABEL,
        "schema": "fixed-shops-offline-v1",
        "created_utc": datetime.now(UTC).isoformat(),
        "altered_environment": SCOPE,
        "runner_sha256": digest(Path(__file__).read_bytes()),
        "source_provenance": source_provenance,
        "donor_manifest_sha256": {path: digest(read_bytes(path)) for path in DONORS.values()},
        "donors": donors,
        "planned_cases": cases,
        "counterfactual_cases": [],
        "complete": False,
    }


def control_comparison(actual, donor):
    """Require complete recorded state/action agreement, not just matching final cash."""
    raw = read_bytes(donor["replay_path"])
    if digest(raw) != donor["replay_sha256"]:
        raise ValueError("Donor replay changed")
    reference = json.loads(raw)
    same_length = len(actual["steps"]) == len(reference["steps"])
    first_state = first_action = None
    for step, (left, right) in enumerate(zip(actual["steps"], reference["steps"], strict=False)):
        if first_state is None and any(
            a["observation"] != b["observation"] for a, b in zip(left, right, strict=True)
        ):
            first_state = step
        if first_action is None and any(
            a["action"] != b["action"] for a, b in zip(left, right, strict=True)
        ):
            first_action = step
    return {
        "step_count_matches": same_length,
        "observations_match": same_length and first_state is None,
        "actions_match": same_length and first_action is None,
        "first_observation_difference": first_state,
        "first_action_difference": first_action,
    }


def run_case(payload):
    """Called only by --run, once per fresh process; no future donor data reaches agents."""
    from kaggle_environments import make

    case, donor, replay_dir = payload
    if digest(read_bytes(case["candidate_path"])) != case["candidate_sha256"]:
        raise ValueError("Frozen candidate changed")
    config = dict(case["configuration"], seed=case["seed"])
    env = make("kaggriculture", configuration=config)
    if dict(env.configuration) != case["configuration"]:
        raise ValueError("Effective diagnostic configuration differs from the donor")
    agents = [case["candidate_path"], case["opponent"]]
    if case["seat"] == 1:
        agents.reverse()
    started = time.perf_counter()
    with (
        FixedShopSchedule(env, donor["schedule"]) as intervention,
        Telemetry(env, case["seat"]) as measured,
    ):
        env.run(agents)
    elapsed = time.perf_counter() - started
    replay = env.toJSON()
    wrapped = {
        **LABEL,
        "case_id": case["case_id"],
        "altered_environment": SCOPE,
        "donor_schedule_sha256": donor["schedule_sha256"],
        "shop_interventions": intervention.events,
        "offline_replay": replay,
    }
    raw = canonical(wrapped)
    path = Path(replay_dir) / (case["case_id"] + ".offline.json.gz")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(gzip.compress(raw, mtime=0))
    runtimes = {}
    for seat in (0, 1):
        values = sorted(log[seat]["duration"] for log in env.logs if len(log) > seat)
        runtimes[str(seat)] = {
            "calls": len(values),
            "max_seconds": max(values, default=0),
            "p99_seconds": values[min(len(values) - 1, int(len(values) * 0.99))] if values else 0,
            **stderr_summary(env.logs, seat),
        }
    cash = [env.steps[-1][seat].reward for seat in (case["seat"], 1 - case["seat"])]
    return {
        **case,
        "seconds": elapsed,
        "final_cash_candidate_opponent": cash,
        "cash_gap": cash[0] - cash[1] if None not in cash else None,
        "statuses": [state.status for state in env.steps[-1]],
        "resolved_seed": env.info.get("seed"),
        "runtime_by_seat": runtimes,
        "candidate_ledger": dict(measured.ledger),
        "candidate_realized_actions": dict(measured.actions),
        "candidate_losses": dict(measured.losses),
        "shop_interventions": intervention.events,
        "donor_policy_control": control_comparison(replay, donor)
        if case["is_donor_policy_control"]
        else None,
        "replay_path": str(path),
        "replay_uncompressed_sha256": digest(raw),
        "replay_archive_sha256": digest(path.read_bytes()),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--run",
        action="store_true",
        help="Execute the sixteen offline cases; otherwise prepare only",
    )
    parser.add_argument("--workers", type=int, default=1)
    parser.add_argument("--output", type=Path, default=Path("data/raw/offline-fixed-shops.json"))
    parser.add_argument("--workdir", type=Path, default=Path("data/interim/fixed-shop-diagnostic"))
    parser.add_argument(
        "--replays", type=Path, default=Path("data/raw/offline-fixed-shops-replays")
    )
    args = parser.parse_args()
    if args.workers < 1:
        parser.error("--workers must be positive")
    if args.output.exists():
        parser.error("Use a new --output path to preserve prior evidence")
    manifest = prepare(args.workdir)
    manifest["execution"] = {
        "requested": args.run,
        "workers": args.workers,
        "fresh_process_per_case": True,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)

    def save():
        args.output.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")

    save()
    if not args.run:
        print(f"Prepared 16 OFFLINE cases without running games: {args.output}")
        return
    tasks = [
        (case, manifest["donors"][case["donor"]], str(args.replays))
        for case in manifest["planned_cases"]
    ]
    with ProcessPoolExecutor(max_workers=args.workers, max_tasks_per_child=1) as pool:
        for result in pool.map(run_case, tasks):
            manifest["counterfactual_cases"].append(result)
            save()
            print(
                "OFFLINE",
                result["case_id"],
                result["final_cash_candidate_opponent"],
                result["statuses"],
                flush=True,
            )
    verify_bundles(manifest["source_provenance"])
    manifest["complete"] = True
    manifest["finished_utc"] = datetime.now(UTC).isoformat()
    save()


if __name__ == "__main__":
    main()
