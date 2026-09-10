"""Build the standalone submission from the exact deployed policy bytes."""

import argparse
import hashlib
import json
from pathlib import Path


def build(destination: Path) -> dict:
    source = Path(__file__).resolve().parents[1] / "src/kaggriculture/agent/competitive.py"
    content = source.read_bytes().replace(b"\r\n", b"\n")
    compile(content, "main.py", "exec")
    destination.mkdir(parents=True, exist_ok=True)
    (destination / "main.py").write_bytes(content)
    manifest = {
        "source": "src/kaggriculture/agent/competitive.py",
        "sha256": hashlib.sha256(content).hexdigest(),
        "bytes": len(content),
    }
    (destination / "manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
    )
    return manifest


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path("submissions/20260909-v8"))
    print(json.dumps(build(parser.parse_args().output), indent=2))
