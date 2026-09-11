"""Profile a declared fleet wall-budget ablation on recorded dense observations."""

import argparse
import gzip
import hashlib
import json
import time
from copy import deepcopy
from pathlib import Path

import numpy as np


def profile(manifest_path, output):
    from kaggle_environments.agent import get_last_callable

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["complete"]
    metadata = next(iter(manifest["candidates"].values()))
    source = gzip.decompress(Path(metadata["snapshot"]).read_bytes()).decode()
    assert hashlib.sha256(source.encode()).hexdigest() == metadata["sha256"]
    assert source.count("deadline = time.perf_counter() + 0.065") == 1
    rows = sorted(manifest["episodes"], key=lambda row: -row["runtime_max_seconds"])[:4]
    states, witnesses = [], []
    for row in rows:
        path = Path(row["replay_path"])
        raw = path.read_bytes()
        replay = json.loads(raw)
        witnesses.append({"path": str(path), "sha256": hashlib.sha256(raw).hexdigest()})
        # Daily reset plus a dense midday state: each is a legal observation,
        # but these independent cold calls do not estimate season trajectories.
        for day in (10, 15, 20, 24, 28, 29):
            for hour in (0, 12):
                step = replay["steps"][24 * day + hour]
                obs = deepcopy(step[0]["observation"])
                obs.update(deepcopy(step[row["seat"]]["observation"]))
                obs["player"] = row["seat"]
                states.append((obs, replay["configuration"]))
    result = {
        "scope": "Cold recorded-state runtime diagnostic; not a match or deployment parity test",
        "input_manifest": str(manifest_path),
        "manifest_sha256": hashlib.sha256(manifest_path.read_bytes()).hexdigest(),
        "replays": witnesses,
        "states": len(states),
        "variants": [],
    }
    for budget in (0.065, 0.150):
        variant = source.replace(
            "deadline = time.perf_counter() + 0.065",
            f"deadline = time.perf_counter() + {budget:.3f}",
        )
        samples, fallbacks, insertions = [], 0, []
        for obs, config in states:
            agent = get_last_callable(variant)
            start = time.perf_counter()
            action = agent(deepcopy(obs), config)
            samples.append(time.perf_counter() - start)
            assert isinstance(action, dict) and "farmer" in action
            stats = agent.__globals__["_DAILY_ROUTE_STATS"]
            fallbacks += stats["budget_fallbacks"]
            insertions.append(stats["insertion_evaluations"])
        result["variants"].append(
            {
                "budget_seconds": budget,
                "sha256": hashlib.sha256(variant.encode()).hexdigest(),
                "runtime_seconds_p50_p95_max": np.quantile(samples, [0.5, 0.95, 1]).tolist(),
                "fallbacks": fallbacks,
                "insertion_evaluations": insertions,
            }
        )
    output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"states": len(states), "variants": result["variants"]}))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    profile(args.input, args.output)
