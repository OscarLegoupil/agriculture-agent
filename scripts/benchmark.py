"""Reproducible official-environment benchmark, with paired seats and telemetry."""

from __future__ import annotations

import argparse
import gzip
import hashlib
import importlib.metadata
import json
import subprocess
import time
from collections import Counter
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

from telemetry import Telemetry


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def snapshot(path):
    """Keep exact candidate bytes without duplicating deployed Python modules."""
    digest = sha(path)
    archive = Path("reports/sources") / (digest + ".py.gz")
    archive.parent.mkdir(parents=True, exist_ok=True)
    archive.write_bytes(gzip.compress(Path(path).read_bytes(), mtime=0))
    return str(archive)


def provenance(paths):
    from kaggle_environments.envs.kaggriculture import kaggriculture as game

    return {
        "revision": subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip(),
        "hashes": {p: sha(p) for p in paths if Path(p).is_file()},
        "environment_version": importlib.metadata.version("kaggle-environments"),
        "interpreter_sha256": sha(game.__file__),
        "lock_sha256": sha("uv.lock"),
        "dependencies": {p: importlib.metadata.version(p) for p in ("numpy", "scipy")},
    }


def episode(args):
    candidate, opponent, seed, seat, replay = args
    from kaggle_environments import make

    start = time.perf_counter()
    env = make("kaggriculture", configuration={"seed": seed, "episodeSteps": 720})
    agents = [candidate, opponent] if seat == 0 else [opponent, candidate]
    with Telemetry(env, seat) as telemetry:
        env.run(agents)
    elapsed = time.perf_counter() - start
    runtimes = sorted(log[seat]["duration"] for log in env.logs if len(log) > seat)
    stderr_turns = sum(bool(log[seat]["stderr"]) for log in env.logs if len(log) > seat)
    daily = []
    actions = Counter()
    for index, step in enumerate(env.steps):
        obs = step[seat].observation
        action = step[seat].action or {}
        for unit in [action.get("farmer", ["PASS"]), *action.get("hands", [])]:
            if unit:
                actions[unit[0]] += 1
        if index % 24 == 0 or index == len(env.steps) - 1:
            farm = obs.farms[seat]
            tiles = [t for row in farm.tiles for t in row if isinstance(t, dict)]
            daily.append(
                {
                    "step": index,
                    "cash": farm.money,
                    "crops": sum(t.get("kind") == "PLANT" for t in tiles),
                    "animals": sum("animal" in t for t in tiles),
                    "composition": dict(
                        Counter(t.get("crop", t.get("animal", t.get("kind"))) for t in tiles)
                    ),
                    "weeds": sum(t.get("kind") == "WEED" for t in tiles),
                    "land": len(farm.unlocked_quadrants),
                    "shed": sum(obs.private.shed.values()),
                    "carried": sum(sum(i.values()) for i in obs.private.inventories),
                }
            )
    replay_path = None
    if replay:
        path = (
            Path(replay) / f"{Path(candidate).parent.name}-{Path(opponent).parent.name}-{Path(opponent).stem}-{seed}-{seat}.json"
        )
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(env.toJSON()), encoding="utf-8")
        replay_path = str(path)
    return {
        "candidate": candidate,
        "opponent": opponent,
        "seed": seed,
        "seat": seat,
        "cash": env.steps[-1][seat].reward,
        "opponent_cash": env.steps[-1][1 - seat].reward,
        "statuses": [s.status for s in env.steps[-1]],
        "seconds": elapsed,
        "configuration": dict(env.configuration),
        "resolved_seed": env.info.get("seed"),
        "daily": daily,
        "requested_actions": dict(actions),
        "realized_actions": dict(telemetry.actions),
        "ledger": dict(telemetry.ledger),
        "losses": dict(telemetry.losses),
        "runtime_max_seconds": max(runtimes, default=0),
        "runtime_p99_seconds": runtimes[min(len(runtimes) - 1, int(len(runtimes) * 0.99))]
        if runtimes
        else 0,
        "stderr_turns": stderr_turns,
        "replay_path": replay_path,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate", required=True)
    parser.add_argument("--opponents", nargs="+", required=True)
    parser.add_argument("--seeds", nargs="+", type=int, default=[0, 17, 42, 103])
    parser.add_argument("--workers", type=int, default=2)
    parser.add_argument("--output", required=True)
    parser.add_argument("--replays")
    parser.add_argument("--replay-seeds", nargs="+", type=int)
    args = parser.parse_args()
    paths = [args.candidate, *args.opponents]
    frozen_candidate = Path("data/interim/frozen") / sha(args.candidate) / "main.py"
    frozen_candidate.parent.mkdir(parents=True, exist_ok=True)
    frozen_candidate.write_bytes(Path(args.candidate).read_bytes())
    manifest = {
        **provenance(paths),
        "candidate_snapshot": snapshot(args.candidate),
        "executed_candidate": str(frozen_candidate),
        "arguments": vars(args),
        "episodes": [],
    }
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    tasks = [
        (str(frozen_candidate), opp, seed, seat,
         args.replays if args.replay_seeds is None or seed in args.replay_seeds else None)
        for opp in args.opponents
        for seed in args.seeds
        for seat in (0, 1)
    ]
    with ProcessPoolExecutor(max_workers=args.workers) as pool:
        for row in pool.map(episode, tasks):
            manifest["episodes"].append(row)
            output.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
            print(
                row["opponent"],
                row["seed"],
                row["seat"],
                row["cash"],
                row["opponent_cash"],
                row["statuses"],
                round(row["seconds"], 2),
                flush=True,
            )


if __name__ == "__main__":
    main()
