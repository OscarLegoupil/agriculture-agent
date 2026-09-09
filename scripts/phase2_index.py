"""Archive phase-two evidence without changing source manifests or raw records."""

import gzip
import hashlib
import json
import re
from collections import defaultdict
from pathlib import Path

ROOT = Path("reports/results")


def digest(content):
    return hashlib.sha256(content).hexdigest()


def normalized(path):
    return str(path).replace("\\", "/")


def read(path):
    content = path.read_bytes()
    return gzip.decompress(content) if path.suffix == ".gz" else content


def excluded(path):
    return "phase2-paired" in str(path)


def main():
    sources = sorted(
        set(Path("data/raw").glob("phase2*.json"))
        | set(Path("data/interim").glob("phase2*/**/*.json"))
    )
    archives = {}
    documents = {}
    for path in sorted(ROOT.glob("phase2*.json.gz")):
        if excluded(path):
            continue
        content = read(path)
        data = json.loads(content)
        if "episodes" not in data or data.get("complete") is False:
            continue
        archives[digest(content)] = path
        documents[digest(content)] = (content, data, [str(path)])
    for path in sources:
        if excluded(path):
            continue
        content = read(path)
        data = json.loads(content)
        if not isinstance(data, dict) or "episodes" not in data or data.get("complete") is False:
            continue
        key = digest(content)
        if key in documents:
            documents[key][2].append(str(path))
        else:
            documents[key] = (content, data, [str(path)])
        if key not in archives:
            stem = (
                path.stem if path.stem.startswith("phase2-") else f"{path.parent.name}-{path.stem}"
            )
            target = ROOT / (stem + ".json.gz")
            if target.exists() and digest(read(target)) != key:
                target = ROOT / (stem + "-" + key[:12] + ".json.gz")
            if not target.exists():
                target.write_bytes(gzip.compress(content, mtime=0))
            assert read(target) == content
            archives[key] = target
    index = {
        "scope": "Completed phase-two experiment manifests selected for curation; phase2-paired and manifests explicitly marked incomplete excluded",
        "counting": "Byte-identical manifest copies count once. Repeated physical scenarios may be reruns or copied subsets, so their count is reported separately without asserting new executions.",
        "manifests": [],
        "warnings": [],
        "repeated_scenarios": [],
    }
    scenarios = defaultdict(list)
    episode_records = set()
    total_rows = error_rows = 0
    seeds = set()
    for key, (_, data, source_paths) in sorted(
        documents.items(), key=lambda item: str(archives[item[0]])
    ):
        hashes = {normalized(p): h for p, h in data.get("hashes", {}).items()}
        candidates = {normalized(p): v for p, v in data.get("candidates", {}).items()}
        checks = {}
        rows = data["episodes"]
        archive = str(archives[key])
        manifest = {
            "archive": archive,
            "sha256_uncompressed": key,
            "source_files": source_paths,
            "episode_rows": len(rows),
            "original_complete_flag": data.get("complete", "not recorded"),
            "seeds": sorted({e["seed"] for e in rows}),
            "statuses": {},
            "candidate_checks": [],
            "opponent_checks": [],
            "recorded_as_rejected_integration": any(
                "default-guard-rejected" in p for p in source_paths
            ),
        }
        for row in rows:
            candidate = normalized(row["candidate"])
            opponent = normalized(row["opponent"])
            metadata = candidates.get(candidate, {})
            snapshot_path = metadata.get(
                "snapshot", data.get("candidate_snapshot", data.get("snapshot"))
            )
            expected = metadata.get("sha256")
            external = isinstance(snapshot_path, dict) and "external_checkout" in snapshot_path
            if external:
                expected = snapshot_path["sha256"]
                snapshot_path = None
            external = external or normalized(
                data.get("arguments", {}).get("candidate", "")
            ).startswith("data/raw/reference-")
            if external:
                snapshot_path = None
            if (
                expected is None
                and data.get("candidate")
                and normalized(data["candidate"]) == candidate
            ):
                expected = data.get("sha256")
            if expected is None:
                original = data.get("arguments", {}).get("candidate", row["candidate"])
                expected = hashes.get(normalized(original), hashes.get(candidate))
            if expected is None and snapshot_path:
                match = re.search(r"([a-f0-9]{64})\.py\.gz$", str(snapshot_path))
                if match:
                    expected = match[1]
            content = None
            if snapshot_path and Path(snapshot_path).exists():
                content = read(Path(snapshot_path))
            elif Path(candidate).exists():
                content = Path(candidate).read_bytes()
            actual = digest(content) if content is not None else None
            if expected is not None and actual != expected:
                index["warnings"].append(
                    {
                        "archive": archive,
                        "candidate": candidate,
                        "expected": expected,
                        "actual": actual,
                    }
                )
            if content is not None and not external and (expected is None or expected == actual):
                snapshot_path = str(Path("reports/sources") / (actual + ".py.gz"))
                snapshot_file = Path(snapshot_path)
                if not snapshot_file.exists():
                    snapshot_file.write_bytes(gzip.compress(content, mtime=0))
                assert read(snapshot_file) == content
            checks[("candidate", candidate)] = {
                "path": candidate,
                "recorded_sha256": expected,
                "verified_sha256": actual,
                "snapshot": snapshot_path,
            }
            opp_expected = hashes.get(opponent)
            opp_actual = digest(Path(opponent).read_bytes()) if Path(opponent).exists() else None
            checks[("opponent", opponent)] = {
                "path": opponent,
                "recorded_sha256": opp_expected,
                "current_file_sha256": opp_actual,
                "matches_recorded": opp_actual == opp_expected if opp_expected else None,
            }
            if opp_expected and opp_actual != opp_expected:
                index["warnings"].append(
                    {
                        "archive": archive,
                        "opponent": opponent,
                        "expected": opp_expected,
                        "actual": opp_actual,
                    }
                )
            states = "/".join(row.get("statuses", []))
            manifest["statuses"][states] = manifest["statuses"].get(states, 0) + 1
            total_rows += 1
            episode_record_hash = digest(json.dumps(row, sort_keys=True).encode())
            episode_records.add(episode_record_hash)
            error_rows += any(s != "DONE" for s in row.get("statuses", []))
            seeds.add(row["seed"])
            candidate_hash = expected or actual or candidate
            opponent_hash = opp_expected or opp_actual or opponent
            players = (
                [candidate_hash, opponent_hash]
                if row["seat"] == 0
                else [opponent_hash, candidate_hash]
            )
            physical = json.dumps(
                [
                    players,
                    row["seed"],
                    data.get("interpreter_sha256"),
                    row.get("configuration", {}),
                ],
                sort_keys=True,
            )
            scenarios[physical].append(
                {
                    "archive": archive,
                    "episode_record_sha256": episode_record_hash,
                    "candidate_sha256": candidate_hash,
                    "seed": row["seed"],
                    "seat": row["seat"],
                    "cash": row["cash"],
                    "opponent_cash": row["opponent_cash"],
                    "statuses": row.get("statuses", []),
                }
            )
        for (kind, _), check in checks.items():
            manifest[kind + "_checks"].append(check)
        index["manifests"].append(manifest)
    for key, records in scenarios.items():
        if len(records) > 1:
            index["repeated_scenarios"].append(
                {
                    "physical_scenario_sha256": digest(key.encode()),
                    "rows": len(records),
                    "role_reversed": len({r["candidate_sha256"] for r in records}) > 1,
                    "records": records,
                }
            )
    index["totals"] = {
        "unique_manifest_bytes": len(documents),
        "recorded_episode_rows": total_rows,
        "unique_episode_records": len(episode_records),
        "identical_episode_copy_rows": total_rows - len(episode_records),
        "non_DONE_rows": error_rows,
        "unique_physical_scenarios": len(scenarios),
        "repeated_scenario_extra_rows": sum(len(v) - 1 for v in scenarios.values()),
        "role_reversed_extra_records": sum(
            max(0, len({r["candidate_sha256"] for r in rows}) - 1) for rows in scenarios.values()
        ),
        "additional_distinct_records_same_orientation": sum(
            len({r["episode_record_sha256"] for r in rows})
            - len({r["candidate_sha256"] for r in rows})
            for rows in scenarios.values()
        ),
        "used_seeds": sorted(seeds),
    }
    index["offline_diagnostics"] = []
    for source in (
        Path("data/interim/phase2-diagnosis/diagnosis.json"),
        Path("data/interim/phase2-economics/market-calibration.json"),
        Path("data/interim/phase2-economics/summary.json"),
    ):
        if not source.exists():
            continue
        content = source.read_bytes()
        target = Path("reports/diagnostics") / f"{source.parent.name}-{source.stem}.json.gz"
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists() and read(target) != content:
            target = target.with_name(
                f"{source.parent.name}-{source.stem}-{digest(content)[:12]}.json.gz"
            )
        if not target.exists():
            target.write_bytes(gzip.compress(content, mtime=0))
        assert read(target) == content
        index["offline_diagnostics"].append(
            {
                "source": str(source),
                "archive": str(target),
                "sha256_uncompressed": digest(content),
                "additional_episode_count": 0,
                "scope": "Existing-game diagnosis or derived summary; excluded from game totals",
            }
        )
    Path("reports/phase2-experiment-index.json").write_text(
        json.dumps(index, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(index["totals"]))
    print("Provenance warnings:", len(index["warnings"]))


if __name__ == "__main__":
    main()
