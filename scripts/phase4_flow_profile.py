"""Profile the frozen joint solver on complete saved trajectories, without games."""

import argparse
import contextlib
import gzip
import hashlib
import io
import json
import time
from pathlib import Path

POLICY = "3d84e710ca80cf761918200746632d895cb9d4911d8fd4f43d924d6cc025fd57"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--replays", type=Path, default=Path("reports/replays/phase4-joint-field"))
    parser.add_argument("--seed", type=int, default=3002)
    parser.add_argument(
        "--output", type=Path, default=Path("reports/results/phase4-flow-profile.json.gz")
    )
    args = parser.parse_args()
    raw = gzip.decompress((Path("reports/sources") / f"{POLICY}.py.gz").read_bytes())
    assert hashlib.sha256(raw).hexdigest() == POLICY
    namespace = {}
    exec(raw, namespace)
    original = namespace["joint_feed_routes"]
    records, inputs, identity = [], [], {}

    def profile(*arguments, **keywords):
        started = time.perf_counter()
        result = original(*arguments, **keywords)
        elapsed = time.perf_counter() - started
        if result is not None:
            assert len({target for target, _ in result}) == len(result)
            assert len({route[1] for _, route in result}) == len(result)
            assert sum(route[3] for _, route in result) <= arguments[3].get("WHEAT", 0)
            assert all(route[-1] >= 0 for _, route in result)
        records.append(
            {
                **identity,
                "pending": len(arguments[0]),
                "workers": len(arguments[1]),
                "wall_seconds": elapsed,
                "fallback": result is None,
            }
        )
        return result

    namespace["joint_feed_routes"] = profile
    paths = sorted(args.replays.glob(f"{POLICY}-*-{args.seed}-0.json"))
    assert len(paths) == 2, "Expected complete COK and Seyam seat-0 trajectories"
    stderr = io.StringIO()
    for path in paths:
        content = path.read_bytes()
        replay = json.loads(content)
        assert replay["statuses"] == ["DONE", "DONE"]
        inputs.append({"path": path.as_posix(), "sha256": hashlib.sha256(content).hexdigest()})
        for state in replay["steps"][:-1]:
            obs = state[0]["observation"]
            identity = {"replay": path.name, "step": obs["step"]}
            with contextlib.redirect_stderr(stderr):
                namespace["agent"](obs, replay["configuration"])
    result = {
        "complete": True,
        "scope": "serial recorded-observation profiling; no game outcomes evaluated",
        "policy_sha256": POLICY,
        "inputs": inputs,
        "calls": len(records),
        "fallback_calls": sum(row["fallback"] for row in records),
        "max_wall_seconds": max(row["wall_seconds"] for row in records),
        "max_pending": max(row["pending"] for row in records),
        "stderr": stderr.getvalue(),
        "records": records,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(gzip.compress((json.dumps(result, indent=2) + "\n").encode(), mtime=0))
    print(json.dumps({k: v for k, v in result.items() if k != "records"}, indent=2))


if __name__ == "__main__":
    main()
