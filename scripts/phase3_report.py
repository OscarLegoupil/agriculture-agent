"""Archive completed development screens and summarize observed matchups."""

import argparse
import gzip
import hashlib
import json
from pathlib import Path
from statistics import mean


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifests", nargs="+", type=Path)
    parser.add_argument(
        "--output", type=Path, default=Path("reports/results/phase3-development.json")
    )
    args = parser.parse_args()
    result = {
        "scope": "Exploratory development only; unequal candidate panels are not directly comparable.",
        "experiments": [],
    }
    for path in args.manifests:
        raw = path.read_bytes()
        if path.suffix == ".gz":
            raw = gzip.decompress(raw)
        manifest = json.loads(raw)
        assert manifest["complete"], f"Unfinished experiment: {path}"
        archive_name = path.name.removesuffix(".gz")
        if not archive_name.startswith("phase3-"):
            archive_name = "phase3-economics-" + archive_name
        archive = args.output.parent / (archive_name + ".gz")
        archive.parent.mkdir(parents=True, exist_ok=True)
        archive.write_bytes(gzip.compress(raw, mtime=0))
        groups = []
        for candidate in sorted({e["candidate"] for e in manifest["episodes"]}):
            metadata = manifest.get("candidates", {}).get(candidate, {})
            digest = metadata.get("sha256", manifest["hashes"].get(candidate))
            assert digest and len(digest) == 64
            frozen = Path("reports/sources") / (digest + ".py.gz")
            assert hashlib.sha256(gzip.decompress(frozen.read_bytes())).hexdigest() == digest
            for opponent in sorted({e["opponent"] for e in manifest["episodes"]}):
                rows = [
                    e
                    for e in manifest["episodes"]
                    if e["candidate"] == candidate and e["opponent"] == opponent
                ]
                scenarios = [(e["seed"], e["seat"]) for e in rows]
                assert len(scenarios) == len(set(scenarios))
                gaps = sorted(e["cash"] - e["opponent_cash"] for e in rows)
                groups.append(
                    {
                        "name": metadata.get("name", manifest.get("name", candidate)),
                        "sha256": digest,
                        "opponent": opponent,
                        "opponent_sha256": manifest["hashes"][opponent],
                        "scenarios": scenarios,
                        "games": len(rows),
                        "wins": sum(g > 0 for g in gaps),
                        "draws": sum(g == 0 for g in gaps),
                        "mean_cash_gap": mean(gaps),
                        "minimum_cash_gap": min(gaps),
                        "mean_cash": mean(e["cash"] for e in rows),
                        "non_done_games": sum(e["statuses"] != ["DONE", "DONE"] for e in rows),
                        "stderr_turns": sum(e["stderr_turns"] for e in rows),
                        "runtime_max_seconds": max(e["runtime_max_seconds"] for e in rows),
                    }
                )
        result["experiments"].append(
            {
                "archive": archive.as_posix(),
                "sha256_uncompressed": hashlib.sha256(raw).hexdigest(),
                "revision": manifest["revision"],
                "groups": groups,
            }
        )
    args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
