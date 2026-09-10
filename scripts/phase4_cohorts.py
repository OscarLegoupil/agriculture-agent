"""Test whether a fixed late opening overrides its own adverse cash forecast."""

import argparse
import gzip
import hashlib
import json
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

from benchmark import episode, provenance, snapshot
from phase2_logistics import replace

BASE = "64fe323936dc9494add413eb956b0294658a88efe28572332c94676c68a09325"
PROFILES = ("economic_after_startup", "guarded_cohort")


def baseline():
    content = gzip.decompress((Path("reports/sources") / (BASE + ".py.gz")).read_bytes())
    assert hashlib.sha256(content).hexdigest() == BASE
    return content.decode()


def build(name):
    source = baseline()
    if name == "economic_after_startup":
        source = replace(source, "        if day < 15:", "        if day < 8:")
    elif name == "guarded_cohort":
        # No new fitted threshold. After day seven a forced cohort must have a
        # positive existing forecast value, at least as good as existing wheat
        # value including the inherited feed bonus. Other ranking is untouched.
        source = replace(
            source,
            "            if current_value > 0:",
            """            if current_value > 0 and (
                day < 8 or (values[cohort_crop] > 0 and values[cohort_crop] >= values["WHEAT"])
            ):""",
        )
    else:
        raise ValueError(name)
    compile(source, name, "exec")
    return source


def check():
    from copy import deepcopy

    from kaggle_environments.envs.kaggriculture import kaggriculture as game
    from kaggle_environments.utils import structify

    replay_path = next(Path("reports/replays/phase4-losses").glob("*3029-0.json"))
    replay = json.loads(replay_path.read_bytes())
    records = []
    for name in ("baseline", *PROFILES):
        source = baseline() if name == "baseline" else build(name)
        # Observe rankings before and after the cohort override, without changing
        # returned actions. This instrumented source is never benchmarked.
        source = replace(
            source,
            "        # Short crops bridge",
            "        original_values = dict(values)\n        # Short crops bridge",
        )
        source = replace(
            source,
            "        crop = max(values, key=lambda c: values[c])",
            "        CHOICES.append((original_values, max(values, key=lambda c: values[c])))\n        crop = max(values, key=lambda c: values[c])",
        )
        namespace = {"CHOICES": []}
        exec(source, namespace)
        obs = deepcopy(replay["steps"][328][0]["observation"])
        action = namespace["agent"](obs)
        choices = namespace["CHOICES"]
        assert choices and choices[-1][0]["STRAWBERRY"] < 0
        if name == "baseline":
            assert choices[-1][1] == "STRAWBERRY"
        else:
            assert all(values[crop] > 0 for values, crop in choices)
            # Replay one alternative BUY_SEED through the official market on
            # the recorded state. This checks legality/cost, not future profit.
            state = structify(deepcopy(replay["steps"][328]))
            crop = choices[-1][1]
            state[0].action = {"market": [["BUY_SEED", crop, 1]]}
            state[1].action = {"market": []}
            before = state[0].observation.farms[0]["money"]
            count = state[0].observation.private["seeds"][crop]
            game._process_market(state, structify({"configuration": replay["configuration"]}))
            assert state[0].observation.private["seeds"][crop] == count + 1
            assert before - state[0].observation.farms[0]["money"] == game.CROPS[crop]["seed"]
        records.append({"name": name, "choices": choices, "action": action})
    # The startup intervention is deliberately absent on all sampled early states.
    namespaces = []
    for source in (baseline(), *(build(name) for name in PROFILES)):
        namespace = {}
        exec(source, namespace)
        namespaces.append(namespace)
    early = 0
    for step in range(0, 192, 11):
        obs = replay["steps"][step][0]["observation"]
        actions = [namespace["agent"](deepcopy(obs)) for namespace in namespaces]
        assert actions[0] == actions[1] == actions[2]
        early += 1
    return {
        "replay": str(replay_path),
        "replay_sha256": hashlib.sha256(replay_path.read_bytes()).hexdigest(),
        "observation_step": 328,
        "early_action_parity_states": early,
        "official_alternative_seed_purchases_checked": 2,
        "choice_probes": records,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--check-only", action="store_true")
    parser.add_argument("--output", type=Path, default=Path("data/raw/phase4-cohorts.json"))
    args = parser.parse_args()
    checks = check()
    print(json.dumps(checks), flush=True)
    if args.check_only:
        return
    opponents = [f"data/raw/reference-{name}/main.py" for name in ("seyam", "cok")]
    manifest = {
        **provenance([*opponents, __file__]),
        "base_sha256": BASE,
        "hypothesis": "After day seven, do not force a cohort whose inherited prospective value is worse than funded short-cycle alternatives",
        "checks": checks,
        "seeds": [3000, 3017, 3042, 3063],
        "candidates": {},
        "episodes": [],
        "complete": False,
    }
    tasks = []
    for name in PROFILES:
        content = build(name).encode()
        digest = hashlib.sha256(content).hexdigest()
        path = Path("data/interim/phase4-cohorts") / name / digest / "main.py"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
        manifest["candidates"][str(path)] = {
            "name": name,
            "sha256": digest,
            "snapshot": snapshot(path),
        }
        tasks.extend(
            (str(path), opponent, seed, seat, None)
            for opponent in opponents
            for seed in manifest["seeds"]
            for seat in (0, 1)
        )
    with ProcessPoolExecutor(max_workers=args.workers) as pool:
        for row in pool.map(episode, tasks):
            manifest["episodes"].append(row)
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
            print(
                manifest["candidates"][row["candidate"]]["name"],
                row["opponent"],
                row["seed"],
                row["seat"],
                row["cash"] - row["opponent_cash"],
                flush=True,
            )
    assert len(manifest["episodes"]) == len(tasks)
    assert len(
        {(e["candidate"], e["opponent"], e["seed"], e["seat"]) for e in manifest["episodes"]}
    ) == len(tasks)
    for path, metadata in manifest["candidates"].items():
        assert hashlib.sha256(Path(path).read_bytes()).hexdigest() == metadata["sha256"]
    manifest["complete"] = True
    args.output.write_text(json.dumps(manifest, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
