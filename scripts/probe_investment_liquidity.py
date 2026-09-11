"""Reproduce bounded official investment prefixes, or summarize saved evidence.

Default: six 48-action continuations from recorded day-five checkpoints, never
full seasons. --summarize-existing only reads a prior prefix manifest.
"""

import argparse
import gzip
import hashlib
import importlib.metadata
import json
import sys
from copy import deepcopy
from pathlib import Path

BASE = "fca083cdb5ac82dc4ad39a4227ef60ca57c948f819b565804aa706994f8e61ba"
OPPONENT = Path("data/raw/reference-mooman/main.py")
SCOPE = "Six 48-action official continuations from recorded step120 through168. Historical baseline controls must reproduce exactly. Both policies receive official shared observations. Opponent is warmed only on prior observed states and responds to changed states; no recorded opponent actions or future draws are forced. These prefixes are not full-game competitive results."


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def read_replay(path):
    if not path.exists():
        path = path.with_suffix(path.suffix + ".gz")
    raw = path.read_bytes()
    return gzip.decompress(raw) if path.suffix == ".gz" else raw


def run_prefixes(replay_dir):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from experiments.daily_routes import build as fleet_build
    from experiments.investment_liquidity import build
    from kaggle_environments import make
    from kaggle_environments.agent import Agent
    from kaggle_environments.envs.kaggriculture import kaggriculture as game
    from kaggle_environments.utils import structify

    variants = {
        "base": fleet_build(cereal=True, budget_seconds=0.150),
        "land": build(seed_capital=False),
        "land_and_seed": build(),
    }
    assert sha(variants["base"].encode()) == BASE
    results, replay_hashes = [], {}
    for seed in (5001, 5002):
        path = replay_dir / f"{BASE}-reference-mooman-main-{seed}-0.json"
        raw = read_replay(path)
        replay_hashes[str(path)] = sha(raw)
        original = json.loads(raw)
        for name, source in variants.items():
            env = make("kaggriculture", configuration=dict(original["configuration"], seed=seed))
            env.steps = structify(deepcopy(original["steps"][:121]))
            env.state = env.steps[-1]
            own, opponent = Agent(source, env), Agent(str(OPPONENT), env)
            for step in original["steps"][:120]:
                env.state = structify(deepcopy(step))
                warmed, log = opponent.act(env._Environment__get_shared_state(1).observation)
                assert not isinstance(warmed, BaseException), log
            env.state = env.steps[-1]
            differences, events, logs, opposing_logs = [], [], [], []
            for step in range(120, 168):
                action, log = own.act(env._Environment__get_shared_state(0).observation)
                other, other_log = opponent.act(env._Environment__get_shared_state(1).observation)
                assert not isinstance(action, BaseException), log
                assert not isinstance(other, BaseException), other_log
                env.step([action, other], [log, other_log])
                logs.append(log)
                opposing_logs.append(other_log)
                assert all(state.status == "ACTIVE" for state in env.state)
                if env.state != original["steps"][step + 1]:
                    differences.append(step + 1)
                farm = env.state[0].observation.farms[0]
                tiles = [t for row in farm["tiles"] for t in row if isinstance(t, dict)]
                events.append(
                    {
                        "step": step + 1,
                        "cash": farm["money"],
                        "land": len(farm["unlocked_quadrants"]),
                        "berries": sum(t.get("crop") == "STRAWBERRY" for t in tiles),
                        "market": action.get("market", []),
                        "farmer": action.get("farmer"),
                        "hands": action.get("hands"),
                        "losses": [
                            t
                            for t in tiles
                            if t.get("consecutive_unfed", 0) > 0
                            or t.get("consecutive_unwatered", 0) > 1
                        ],
                    }
                )
            record = {
                "seed": seed,
                "seat": 0,
                "name": name,
                "source_sha256": sha(source.encode()),
                "configuration": dict(env.configuration),
                "resolved_seed": env.info["seed"],
                "first_difference": min(differences, default=None),
                "events": events,
                "stderr": [entry["stderr"] for entry in logs if entry["stderr"]],
                "opponent_stderr": [entry["stderr"] for entry in opposing_logs if entry["stderr"]],
                "runtime_max": max(entry["duration"] for entry in logs),
            }
            results.append(record)
            print(seed, name, "prefix complete", flush=True)
    assert all(row["first_difference"] is None for row in results if row["name"] == "base")
    sources = [
        Path(__file__),
        Path("experiments/investment_liquidity.py"),
        Path("experiments/daily_routes.py"),
        *OPPONENT.parent.glob("*.py"),
        OPPONENT.parent / "actions.json",
    ]
    return {
        "evidence_kind": "official_checkpoint_prefix",
        "competitive_score_eligible": False,
        "scope": SCOPE,
        "environment_version": importlib.metadata.version("kaggle-environments"),
        "interpreter_sha256": sha(Path(game.__file__).read_bytes()),
        "replay_sha256": replay_hashes,
        "source_sha256": {str(path): sha(path.read_bytes()) for path in sources},
        "prefixes": results,
    }


def summarize(manifest, input_hash):
    assert manifest["evidence_kind"] == "official_checkpoint_prefix"
    assert manifest["competitive_score_eligible"] is False
    rows = manifest["prefixes"]
    assert len(rows) == 6 and {(r["seed"], r["seat"], r["name"]) for r in rows} == {
        (seed, 0, name) for seed in (5001, 5002) for name in ("base", "land", "land_and_seed")
    }
    assert all(r["first_difference"] is None for r in rows if r["name"] == "base")
    result = {key: value for key, value in manifest.items() if key != "prefixes"}
    result.update(
        raw_manifest_sha256=input_hash,
        summary_script_sha256=sha(Path(__file__).read_bytes()),
        reproduction="python scripts/probe_investment_liquidity.py",
        inspection="python scripts/probe_investment_liquidity.py --summarize-existing data/raw/frontier-20260911/investment-liquidity-prefix.json",
        prefixes=[],
    )
    for row in rows:
        events = row["events"]
        assert [event["step"] for event in events] == list(range(121, 169))
        result["prefixes"].append(
            {
                **{key: value for key, value in row.items() if key != "events"},
                "land_purchase_steps": [e["step"] for e in events if ["BUY_LAND"] in e["market"]],
                "first_berry_step": next((e["step"] for e in events if e["berries"]), None),
                "berries_at_168": events[-1]["berries"],
                "cash_at_168": events[-1]["cash"],
                "maximum_observed_unfed_animals": max(
                    sum("animal" in tile for tile in e["losses"]) for e in events
                ),
            }
        )
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--summarize-existing", type=Path)
    parser.add_argument("--replays", type=Path, default=Path("reports/replays/breakthrough"))
    parser.add_argument(
        "--raw-output", type=Path, default=Path("data/raw/investment-liquidity-prefix.json")
    )
    parser.add_argument(
        "--output", type=Path, default=Path("reports/results/investment-liquidity-prefix.json")
    )
    args = parser.parse_args()
    if args.summarize_existing:
        raw = args.summarize_existing.read_bytes()
        manifest = json.loads(raw)
    else:
        if args.raw_output.exists():
            parser.error("Use a new --raw-output path to preserve existing prefix evidence")
        manifest = run_prefixes(args.replays)
        raw = (json.dumps(manifest, indent=2) + "\n").encode()
        args.raw_output.parent.mkdir(parents=True, exist_ok=True)
        args.raw_output.write_bytes(raw)
    result = summarize(manifest, sha(raw))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print("Saved prefix evidence", args.output)


if __name__ == "__main__":
    main()
