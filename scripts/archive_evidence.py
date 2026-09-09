"""Compress completed per-game evidence while keeping summaries readable."""

import gzip
import hashlib
import json
from pathlib import Path


def main():
    root = Path("reports/results").resolve()
    manifest = {}
    for path in sorted(root.glob("*.json")):
        content = path.read_bytes()
        data = json.loads(content)
        if "episodes" not in data or "environment_version" not in data:
            continue
        compressed = gzip.compress(content, mtime=0)
        assert gzip.decompress(compressed) == content
        target = path.with_suffix(".json.gz")
        target.write_bytes(compressed)
        # Only this verified file is removed; its exact bytes remain in gzip.
        assert path.parent == root
        path.unlink()
    for path in sorted(root.glob("*.json.gz")):
        content = gzip.decompress(path.read_bytes())
        data = json.loads(content)
        benchmark = "episodes" in data and "environment_version" in data
        manifest[path.name] = {
            "sha256_uncompressed": hashlib.sha256(content).hexdigest(),
            "bytes": path.stat().st_size,
            "games": len(data.get("episodes", [])) if benchmark else 0,
            "kind": "benchmark" if benchmark else "analysis",
        }
    (root / "index.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
