"""Rebuild the frozen research challenger; this does not promote a submission."""

import argparse
import hashlib
import json
from pathlib import Path

from phase2_correctness import build

DIGEST = "0098d9e4f77e2420cb4a09abd47e49f5160009cd0818ae37a793bc3e419ffc4b"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path("data/interim/phase2-challenger"))
    args = parser.parse_args()
    content = build("liquidity_model_expand").encode()
    assert hashlib.sha256(content).hexdigest() == DIGEST, "Frozen challenger builder changed"
    compile(content, "main.py", "exec")
    args.output.mkdir(parents=True, exist_ok=True)
    (args.output / "main.py").write_bytes(content)
    manifest = {
        "status": "research-only; challenge promotion gate failed",
        "builder": "scripts/phase2_correctness.py:build(liquidity_model_expand)",
        "incumbent": "submissions/20260909-v7/main.py",
        "sha256": DIGEST,
    }
    (args.output / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
