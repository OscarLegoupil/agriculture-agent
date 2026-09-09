"""Archive completed development screens and summarize observed matchups."""

import argparse
import gzip
import hashlib
import json
import math
from pathlib import Path
from statistics import mean

try:
    from .summarize_benchmark import match_score
except ImportError:
    from summarize_benchmark import match_score


def normalized(path):
    return str(path).replace("\\", "/")


def candidate_identity(manifest, candidate):
    """Resolve a recorded executable, never infer identity from an unrelated hash."""
    hashes = {normalized(p): digest for p, digest in manifest["hashes"].items()}
    candidates = {normalized(p): meta for p, meta in manifest.get("candidates", {}).items()}
    path = normalized(candidate)
    if path in candidates:
        metadata = candidates[path]
        return metadata["sha256"], metadata.get("name", candidate)
    if normalized(manifest.get("candidate", "")) == path and "sha256" in manifest:
        return manifest["sha256"], manifest.get("name", manifest.get("objective", candidate))
    if normalized(manifest.get("executed_candidate", "")) == path:
        submitted = normalized(manifest["arguments"]["candidate"])
        return hashes[submitted], manifest.get("name", candidate)
    assert path in hashes, f"No recorded hash for executed candidate: {candidate}"
    return hashes[path], manifest.get("name", candidate)


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
    pending = {}
    for path in args.manifests:
        raw = path.read_bytes()
        if path.suffix == ".gz":
            raw = gzip.decompress(raw)
        manifest = json.loads(raw)
        assert manifest["complete"], f"Unfinished experiment: {path}"
        archive_name = path.name.removesuffix(".gz")
        if not archive_name.startswith("phase3-"):
            prefix = path.parent.name if path.parent.name.startswith("phase3-") else "phase3"
            archive_name = prefix + "-" + archive_name
        archive = args.output.parent / (archive_name + ".gz")
        if archive.exists():
            assert gzip.decompress(archive.read_bytes()) == raw, f"Archive collision: {archive}"
        if archive in pending:
            assert pending[archive] == raw, f"Input basename collision: {archive}"
        pending[archive] = raw
        groups = []
        for candidate in sorted({e["candidate"] for e in manifest["episodes"]}):
            digest, name = candidate_identity(manifest, candidate)
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
                cash_rows = [
                    e
                    for e in rows
                    if all(
                        e.get(key) is not None and math.isfinite(e[key])
                        for key in ("cash", "opponent_cash")
                    )
                ]
                gaps = sorted(e["cash"] - e["opponent_cash"] for e in cash_rows)
                scores = [match_score(e) for e in rows]
                groups.append(
                    {
                        "name": name,
                        "sha256": digest,
                        "opponent": opponent,
                        "opponent_sha256": manifest["hashes"][opponent],
                        "scenarios": scenarios,
                        "games": len(rows),
                        "wins": sum(s == 1 for s in scores),
                        "draws": sum(s == 0.5 for s in scores),
                        "match_score": mean(scores),
                        "mean_cash_gap": mean(gaps) if gaps else None,
                        "minimum_cash_gap": min(gaps) if gaps else None,
                        "missing_cash_games": len(rows) - len(cash_rows),
                        "mean_cash": mean(e["cash"] for e in cash_rows) if cash_rows else None,
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
    # Do not mutate the evidence directory until every input and source validates.
    args.output.parent.mkdir(parents=True, exist_ok=True)
    for archive, raw in pending.items():
        archive.write_bytes(gzip.compress(raw, mtime=0))
    args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
