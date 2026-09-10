"""Compare two reviewed policies on saved observations without running games.

The raw view combines shared replay fields with the selected player's private
state. The external view uses the official environment's hidden-field filter.
This checks action equivalence on recorded states, not whole-game trajectories.
"""

import argparse
import contextlib
import copy
import gzip
import hashlib
import io
import json
import time
from pathlib import Path


def load_policy(path):
    content = path.read_bytes()
    if path.suffix == ".gz":
        content = gzip.decompress(content)
    namespace = {"__name__": "policy_refactor_check"}
    exec(compile(content, str(path), "exec"), namespace)
    identity = {
        "path": path.as_posix(),
        "executed_sha256": hashlib.sha256(content).hexdigest(),
        "lf_normalized_sha256": hashlib.sha256(content.replace(b"\r\n", b"\n")).hexdigest(),
    }
    return namespace["agent"], identity


def save(path, report):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")


def compare(original, candidate, paths, output, stride=1):
    from kaggle_environments import make
    from kaggle_environments.utils import structify

    left, original_identity = load_policy(original)
    right, candidate_identity = load_policy(candidate)
    started = time.perf_counter()
    report = {
        "original": original_identity,
        "candidate": candidate_identity,
        "complete": False,
        "step_stride": stride,
        "scope": "Saved-observation action parity only; no new games or trajectory equivalence claim",
        "results": [],
    }
    save(output, report)
    stderr = io.StringIO()
    for path in paths:
        content = path.read_bytes()
        replay = json.loads(content.decode("utf-8"))
        seat = int(path.stem.rsplit("-", 1)[1])
        env = make("kaggriculture", configuration=replay["configuration"])
        counts = {"raw_private_shared": 0, "external": 0}
        for index in range(0, len(replay["steps"]) - 1, stride):
            row = replay["steps"][index]
            env.state = structify(copy.deepcopy(row))
            external = env._Environment__get_shared_state(seat)["observation"]
            raw = copy.deepcopy(row[seat]["observation"])
            properties = env._Environment__state_schema.properties.observation.properties
            for key, prop in properties.items():
                if prop.get("shared", False):
                    raw[key] = copy.deepcopy(row[0]["observation"][key])
            actions = []
            for form, observation in (("raw_private_shared", raw), ("external", external)):
                with contextlib.redirect_stderr(stderr):
                    expected = left(copy.deepcopy(observation), replay["configuration"])
                    actual = right(copy.deepcopy(observation), replay["configuration"])
                if expected != actual:
                    report["first_difference"] = {
                        "replay": path.as_posix(),
                        "step": index,
                        "form": form,
                        "original": expected,
                        "candidate": actual,
                    }
                    report["stderr"] = stderr.getvalue()
                    save(output, report)
                    raise AssertionError(f"Action difference: {path.name}, step {index}, {form}")
                counts[form] += 1
                actions.append(actual)
            if actions[0] != actions[1]:
                raise AssertionError(f"Raw/external views differ: {path.name}, step {index}")
        report["results"].append(
            {
                "replay": path.as_posix(),
                "replay_sha256": hashlib.sha256(content).hexdigest(),
                "seat": seat,
                "comparisons": counts,
            }
        )
        save(output, report)
        print(path.name, counts, flush=True)
    report.update(
        complete=True,
        seconds=time.perf_counter() - started,
        stderr=stderr.getvalue(),
        total_comparisons=sum(sum(row["comparisons"].values()) for row in report["results"]),
    )
    save(output, report)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--original", required=True, type=Path, help="Reviewed .py or .py.gz source"
    )
    parser.add_argument("--candidate", required=True, type=Path)
    parser.add_argument("--replays", required=True, type=Path)
    parser.add_argument("--seeds", nargs="+", type=int, default=[2002, 2009])
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument(
        "--step-stride", type=int, default=1, help="1 checks every executable observation"
    )
    args = parser.parse_args()
    if args.step_stride < 1:
        parser.error("--step-stride must be positive")
    paths = sorted(
        path
        for path in args.replays.glob("*.json")
        if path.stem.rsplit("-", 2)[1] in {str(seed) for seed in args.seeds}
    )
    if not paths:
        parser.error("No saved replays match the requested seeds")
    report = compare(args.original, args.candidate, paths, args.output, args.step_stride)
    print(f"Matched {report['total_comparisons']} action comparisons")


if __name__ == "__main__":
    main()
