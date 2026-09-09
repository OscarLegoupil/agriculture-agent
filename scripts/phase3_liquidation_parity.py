"""Compare the final-order correction on ten saved observation trajectories; no games."""

import argparse
import gzip
import hashlib
import json
from copy import deepcopy
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--reference",
        type=Path,
        default=Path(
            "reports/sources/d7a816d4fa82be8a781c2d4c9ee845eb6062c8468cc3eb7013fb2c66cb45902a.py.gz"
        ),
    )
    parser.add_argument("--artifact", type=Path, default=Path("submissions/20260909-v8/main.py"))
    parser.add_argument(
        "--output", type=Path, default=Path("reports/results/phase3-liquidation-parity.json")
    )
    args = parser.parse_args()
    paths = [
        Path(x["replay"])
        for x in json.loads(Path("reports/results/phase3-release-parity.json").read_bytes())[
            "results"
        ][:10]
    ]
    old = gzip.decompress(args.reference.read_bytes())
    new = args.artifact.read_bytes()
    namespaces = []
    for source in (old, new):
        n = {}
        exec(source, n)
        namespaces.append(n)
    results = []
    for path in paths:
        raw = path.read_bytes()
        r = json.loads(raw)
        seat = int(path.stem[-1])
        diff = []
        for idx, step in enumerate(r["steps"][:-1]):
            obs = deepcopy(step[0]["observation"])
            obs.update(step[seat]["observation"])
            obs.update(player=seat, step=idx)
            a, b = [n["agent"](deepcopy(obs), r["configuration"]) for n in namespaces]
            if a != b:
                diff.append(
                    {"step": idx, "day": obs["day"], "hour": obs["hour"], "old": a, "new": b}
                )
        results.append(
            {
                "replay": str(path).replace("\\", "/"),
                "replay_sha256": hashlib.sha256(raw).hexdigest(),
                "seat": seat,
                "actions_compared": len(r["steps"]) - 1,
                "differences": diff,
            }
        )
        print(path.name, len(diff), flush=True)
    report = {
        "old_sha256": hashlib.sha256(old).hexdigest(),
        "new_sha256": hashlib.sha256(new).hexdigest(),
        "scope": "Saved-observation action comparison, no new games",
        "complete": True,
        "results": results,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
