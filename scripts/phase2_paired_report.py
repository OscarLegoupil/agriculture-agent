"""Reconstruct the six-seed exploratory comparison from exact saved records."""

import argparse
import gzip
import hashlib
import json
from pathlib import Path

from evidence_io import read_result
from phase2_compare import compare

OLD = "750f123073865347efd3b9c4b72022ff9923f4130c929ac76c1b0742374b09ee"
NEW = "0098d9e4f77e2420cb4a09abd47e49f5160009cd0818ae37a793bc3e419ffc4b"
SEEDS = {0, 17, 42, 103, 5, 11}
OPPONENTS = [f"data/raw/reference-{name}/main.py" for name in ("lonespear", "gzm", "seyam", "cok")]
SOURCES = [
    "audit-final-v7",
    "phase2-frontier-screen",
    "phase2-incumbent-extra-anchors",
    "phase2-best-anchors",
    "phase2-interactions",
    "phase2-interaction-development",
]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output", type=Path, default=Path("reports/results/phase2-paired-summary.json")
    )
    args = parser.parse_args()
    panels = {OLD: {}, NEW: {}}
    hashes, metadata, inputs = {}, None, {}
    for stem in SOURCES:
        path = Path("reports/results") / (stem + ".json.gz")
        record = read_result(path)
        inputs[str(path)] = hashlib.sha256(gzip.decompress(path.read_bytes())).hexdigest()
        provenance = {
            k: record[k] for k in ("environment_version", "interpreter_sha256", "lock_sha256")
        }
        if metadata is not None:
            assert metadata == provenance
        metadata = provenance
        for opponent in OPPONENTS:
            if opponent in record["hashes"]:
                digest = record["hashes"][opponent]
                assert hashes.get(opponent, digest) == digest
                hashes[opponent] = digest
        for row in record["episodes"]:
            if row["seed"] not in SEEDS or row["opponent"] not in OPPONENTS:
                continue
            candidate = row["candidate"]
            info = record.get("candidates", {}).get(candidate, {})
            digest = info.get("sha256", record["hashes"].get(candidate))
            if digest is None:
                # Generic benchmark executes a content-addressed frozen copy.
                digest = Path(candidate.replace("\\", "/")).parent.name
            if digest not in panels:
                continue
            snapshot = Path("reports/sources") / (digest + ".py.gz")
            assert hashlib.sha256(gzip.decompress(snapshot.read_bytes())).hexdigest() == digest
            key = row["opponent"], row["seed"], row["seat"]
            if key in panels[digest]:
                previous = panels[digest][key]
                # Reproductions must agree; they are never additional evidence.
                for field in (
                    "cash",
                    "opponent_cash",
                    "statuses",
                    "configuration",
                    "resolved_seed",
                ):
                    assert previous[field] == row[field], (key, field)
                continue
            panels[digest][key] = row
    assert all(len(panel) == 48 for panel in panels.values())
    report = {
        "purpose": "Exploratory development evidence; selected on these seeds, not fresh validation",
        "incumbent_sha256": OLD,
        "challenger_sha256": NEW,
        "inputs_sha256_uncompressed": inputs,
        "opponent_hashes": hashes,
        **metadata,
    }
    for name, opponents in (("anchor", OPPONENTS[:2]), ("challenge", OPPONENTS[2:])):
        rows = [
            [r for r in panel.values() if r["opponent"] in opponents] for panel in panels.values()
        ]
        report[name] = compare(*rows, dict.fromkeys(opponents, 0.5))
    args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(
        json.dumps({name: report[name]["aggregate"] for name in ("anchor", "challenge")}, indent=2)
    )


if __name__ == "__main__":
    main()
