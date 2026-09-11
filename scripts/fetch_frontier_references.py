"""Restore reviewed multi-file opponents from immutable, hash-verified sources."""

import hashlib
import json
import urllib.request
from pathlib import Path


def main():
    manifest = json.loads(Path("reports/frontier-20260911/references.json").read_text())
    root = Path("data/raw").resolve()
    for reference in manifest["references"]:
        directory = root / ("reference-" + reference["name"])
        for entry in reference["files"]:
            target = (directory / entry["relative_path"]).resolve()
            if not target.is_relative_to(directory):
                raise ValueError("Reference path escapes its isolated directory")
            if target.exists():
                content = target.read_bytes()
            elif "local_source" in entry:
                content = Path(entry["local_source"]).read_bytes()
            else:
                with urllib.request.urlopen(entry["url"], timeout=30) as response:
                    content = response.read()
            if hashlib.sha256(content).hexdigest() != entry["sha256"]:
                raise ValueError(f"Reference differs from reviewed bytes: {target}")
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(content)
        print(reference["name"], reference["revision"], len(reference["files"]), "verified files")


if __name__ == "__main__":
    main()
