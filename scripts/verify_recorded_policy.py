"""Verify stateful source/artifact parity on complete recorded observation streams.

No games are simulated. Each clean process sees both seats, then the first
episode again to test disposal at step zero. RSS is measured without tracing
overhead that would change the policy's wall-budget behavior.
"""

import argparse
import hashlib
import inspect
import json
import subprocess
import sys
import tempfile
import time
from copy import deepcopy
from pathlib import Path

from verify_submission import memory_usage


def verify(source, artifact, replays, output):
    from kaggle_environments.agent import get_last_callable

    source_bytes = source.read_bytes().replace(b"\r\n", b"\n")
    content = artifact.read_bytes()
    assert source_bytes == content, "Fresh build differs from frozen artifact"
    loaded = get_last_callable(content.decode())
    namespace = {}
    exec(source_bytes, namespace)
    assert loaded.__code__ == namespace["agent"].__code__
    report = {
        "scope": "Complete recorded-state parity and process-reset checks; no new match outcomes",
        "source": str(source),
        "artifact": str(artifact),
        "sha256": hashlib.sha256(content).hexdigest(),
        "replays": [],
        "source_recorded_mismatches": [],
        "source_official_loader_mismatches": [],
        "source_budget_fallback_indices": [],
        "isolated_mismatches": [],
        "source_runtime_max_seconds": 0.0,
        "isolated_processes": [],
    }
    expected = []
    with tempfile.TemporaryDirectory() as directory:
        temporary = Path(directory)
        (temporary / "main.py").write_bytes(content)
        payload = temporary / "observations.jsonl"
        with payload.open("w", encoding="utf-8") as stream:
            for path, seat in [*replays, replays[0]]:
                raw = path.read_bytes()
                replay = json.loads(raw)
                report["replays"].append(
                    {"path": str(path), "seat": seat, "sha256": hashlib.sha256(raw).hexdigest()}
                )
                for step in replay["steps"][:-1]:
                    observation = deepcopy(step[0]["observation"])
                    observation.update(deepcopy(step[seat]["observation"]))
                    observation["player"] = seat
                    config = replay["configuration"]
                    started = time.perf_counter()
                    prior_fallbacks = namespace.get("_DAILY_ROUTE_STATS", {}).get(
                        "budget_fallbacks", 0
                    )
                    decision = namespace["agent"](deepcopy(observation), config)
                    report["source_runtime_max_seconds"] = max(
                        report["source_runtime_max_seconds"], time.perf_counter() - started
                    )
                    official = loaded(deepcopy(observation), config)
                    index = len(expected)
                    if (
                        namespace.get("_DAILY_ROUTE_STATS", {}).get("budget_fallbacks", 0)
                        != prior_fallbacks
                    ):
                        report["source_budget_fallback_indices"].append(index)
                    if decision != official:
                        report["source_official_loader_mismatches"].append(index)
                    recorded = replay["steps"][observation["step"] + 1][seat]["action"]
                    if decision != recorded:
                        report["source_recorded_mismatches"].append(index)
                    expected.append(decision)
                    stream.write(json.dumps([observation, config]) + "\n")
        child = (
            inspect.getsource(memory_usage)
            + "\n"
            + """
import json, runpy, sys, time
namespace = runpy.run_path('main.py')
peak = 0
for index, line in enumerate(sys.stdin):
    observation, config = json.loads(line)
    started = time.perf_counter()
    action = namespace['agent'](observation, config)
    peak = max(peak, time.perf_counter() - started)
    print(json.dumps({'index': index, 'action': action}))
print(json.dumps({'memory': memory_usage(), 'runtime_max_seconds': peak}))
"""
        )
        for process in range(2):
            with payload.open(encoding="utf-8") as stream:
                result = subprocess.run(
                    [sys.executable, "-I", "-S", "-c", child],
                    cwd=temporary,
                    stdin=stream,
                    capture_output=True,
                    text=True,
                    check=True,
                )
            lines = [json.loads(line) for line in result.stdout.splitlines()]
            memory = lines.pop()
            assert len(lines) == len(expected)
            for row in lines:
                if row["action"] != expected[row["index"]]:
                    report["isolated_mismatches"].append([process, row["index"]])
            report["isolated_processes"].append(
                {**memory, "stderr": result.stderr.splitlines(), "actions": len(lines)}
            )
    report["actions_per_process"] = len(expected)
    report["passed"] = not any(
        report[key]
        for key in (
            "source_recorded_mismatches",
            "source_official_loader_mismatches",
            "isolated_mismatches",
        )
    )
    report["memory_note"] = (
        "Clean executable process RSS includes interpreter and one decoded observation; no allocation tracer. Parent replay-loading memory is excluded."
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report))
    return report["passed"]


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--artifact", type=Path, required=True)
    parser.add_argument(
        "--replay", nargs=2, action="append", required=True, metavar=("PATH", "SEAT")
    )
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    success = verify(
        args.source,
        args.artifact,
        [(Path(path), int(seat)) for path, seat in args.replay],
        args.output,
    )
    sys.exit(0 if success else 1)
