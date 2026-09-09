"""Compare the declared 16-seed development field to the frozen incumbent."""

import argparse
import hashlib
import json
from copy import deepcopy
from pathlib import Path

from evidence_io import read_result
from phase2_compare import compare_manifests


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--incumbent",
        type=Path,
        default=Path("reports/results/phase2-validation-challenger.json.gz"),
    )
    parser.add_argument(
        "--challenger", type=Path, default=Path("data/raw/phase3-opening-field.json")
    )
    parser.add_argument(
        "--output", type=Path, default=Path("reports/results/phase3-opening-field-summary.json")
    )
    args = parser.parse_args()
    original, candidate = read_result(args.incumbent), read_result(args.challenger)
    assert original["complete"] and candidate["complete"]
    seeds = list(range(2000, 2016))
    assert sorted({r["seed"] for r in candidate["episodes"]}) == seeds
    incumbent = deepcopy(original)
    incumbent["episodes"] = [r for r in original["episodes"] if r["seed"] in seeds]
    groups = {
        "anchor": ["lonespear", "gzm"],
        "challenge": ["seyam", "cok"],
        "equal_four": ["lonespear", "gzm", "seyam", "cok"],
    }
    result = {
        "scope": "Known development seeds; exploratory candidate confirmation, not fresh validation.",
        "incumbent_parent": {
            "path": args.incumbent.as_posix(),
            "file_sha256": hashlib.sha256(args.incumbent.read_bytes()).hexdigest(),
            "original_games": len(original["episodes"]),
            "selected_seeds": seeds,
        },
        "challenger_manifest_sha256": hashlib.sha256(args.challenger.read_bytes()).hexdigest(),
        "pools": {},
    }
    for name, opponents in groups.items():
        weights = {f"data/raw/reference-{opp}/main.py": 1 / len(opponents) for opp in opponents}
        result["pools"][name] = compare_manifests(incumbent, candidate, weights)
        print(name, json.dumps(result["pools"][name]["aggregate"]))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
