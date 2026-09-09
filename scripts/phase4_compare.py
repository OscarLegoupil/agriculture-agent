"""Compare an explicitly declared known-data subset, preserving parent provenance."""

import argparse
import hashlib
import json
from pathlib import Path

try:
    from .evidence_io import read_result
    from .phase2_compare import compare_manifests, indexed
except ImportError:
    from evidence_io import read_result
    from phase2_compare import compare_manifests, indexed


def subset(manifest, opponents, seeds):
    expected = {(o, s, seat) for o in opponents for s in seeds for seat in (0, 1)}
    rows = indexed(manifest["episodes"])
    if not expected or not expected <= rows.keys():
        raise ValueError("Declared subset is empty or missing scenarios")
    if any(rows[key].get("resolved_seed") != key[1] for key in expected):
        raise ValueError("Resolved seed differs from declared seed")
    return {**manifest, "episodes": [rows[key] for key in sorted(expected)]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("incumbent", type=Path)
    parser.add_argument("challenger", type=Path)
    parser.add_argument("--seeds", nargs="+", type=int, required=True)
    parser.add_argument("--opponents", nargs="+", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    opponents, seeds = sorted(set(args.opponents)), sorted(set(args.seeds))
    parents = [read_result(path) for path in (args.incumbent, args.challenger)]
    report = compare_manifests(
        *(subset(parent, opponents, seeds) for parent in parents),
        dict.fromkeys(opponents, 1 / len(opponents)),
    )
    report["scope"] = {
        "kind": "known-data development comparison; no fresh selection claim",
        "opponents": opponents,
        "seeds": seeds,
        "seats": [0, 1],
        "parents": {
            role: {
                "path": str(path),
                "file_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                "total_games": len(parent["episodes"]),
            }
            for role, path, parent in zip(
                ("incumbent", "challenger"), (args.incumbent, args.challenger), parents, strict=True
            )
        },
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report["aggregate"], indent=2))


if __name__ == "__main__":
    main()
