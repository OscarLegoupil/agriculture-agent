"""Reproducible official-environment benchmark, with paired seats and telemetry."""

from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import subprocess
import time
from collections import Counter
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def episode(args):
    candidate, opponent, seed, seat, replay = args
    from kaggle_environments import make

    start = time.perf_counter()
    env = make("kaggriculture", configuration={"seed": seed, "episodeSteps": 720})
    agents = [candidate, opponent] if seat == 0 else [opponent, candidate]
    env.run(agents)
    elapsed = time.perf_counter() - start
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
            daily.append({"step": index, "cash": farm.money,
                          "crops": sum(t.get("kind") == "PLANT" for t in tiles),
                          "animals": sum("animal" in t for t in tiles),
                          "weeds": sum(t.get("kind") == "WEED" for t in tiles),
                          "land": len(farm.unlocked_quadrants),
                          "shed": sum(obs.private.shed.values()),
                          "carried": sum(sum(i.values()) for i in obs.private.inventories)})
    if replay:
        path = Path(replay) / f"{Path(candidate).parent.name}-{Path(opponent).stem}-{seed}-{seat}.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(env.toJSON()), encoding="utf-8")
    return {"candidate": candidate, "opponent": opponent, "seed": seed, "seat": seat,
            "cash": env.steps[-1][seat].reward, "opponent_cash": env.steps[-1][1-seat].reward,
            "statuses": [s.status for s in env.steps[-1]], "seconds": elapsed,
            "configuration": dict(env.configuration), "resolved_seed": env.info.get("seed"),
            "daily": daily, "requested_actions": dict(actions)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate", required=True)
    parser.add_argument("--opponents", nargs="+", required=True)
    parser.add_argument("--seeds", nargs="+", type=int, default=[0, 17, 42, 103])
    parser.add_argument("--workers", type=int, default=2)
    parser.add_argument("--output", required=True)
    parser.add_argument("--replays")
    args = parser.parse_args()
    import kaggle_environments.envs.kaggriculture.kaggriculture as game

    paths = [args.candidate, *args.opponents]
    manifest = {"revision": subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip(),
                "hashes": {p: sha(p) for p in paths if Path(p).is_file()},
                "environment_version": importlib.metadata.version("kaggle-environments"),
                "interpreter_sha256": sha(game.__file__), "arguments": vars(args), "episodes": []}
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    tasks = [(args.candidate, opp, seed, seat, args.replays)
             for opp in args.opponents for seed in args.seeds for seat in (0, 1)]
    with ProcessPoolExecutor(max_workers=args.workers) as pool:
        for row in pool.map(episode, tasks):
            manifest["episodes"].append(row)
            output.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
            print(row["opponent"], row["seed"], row["seat"], row["cash"], row["opponent_cash"],
                  row["statuses"], round(row["seconds"], 2), flush=True)


if __name__ == "__main__":
    main()
