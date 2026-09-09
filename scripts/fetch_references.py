"""Fetch reviewed public executables at immutable revisions for local evaluation."""

import json
import subprocess
from pathlib import Path

REFERENCES = {
    "lonespear": (
        "https://github.com/lonespear/kaggriculture.git",
        "774b26093ccf4246525517d48420349b841b6e50",
        "main.py",
    ),
    "gzm": (
        "https://github.com/GzmCR/Kaggriculture.git",
        "6a76335397d5cd2facffa91c938f629b119ea350",
        "main.py",
    ),
    "tina": (
        "https://github.com/TinaawhyteD/kaggriculture-agent.git",
        "169ca945b3358cd85baa71260e9c17dc0ebe5555",
        "agent.py",
    ),
}


def main():
    from benchmark import sha

    manifest = {}
    for name, (url, revision, executable) in REFERENCES.items():
        directory = Path("data/raw") / ("reference-" + name)
        if not directory.exists():
            subprocess.run(["git", "clone", url, str(directory)], check=True)
        current = subprocess.check_output(
            ["git", "-C", str(directory), "rev-parse", "HEAD"], text=True
        ).strip()
        if current != revision:
            dirty = subprocess.check_output(
                ["git", "-C", str(directory), "status", "--porcelain"], text=True
            )
            if dirty:
                raise RuntimeError(f"Reference checkout has local changes: {directory}")
            subprocess.run(["git", "-C", str(directory), "checkout", revision], check=True)
        manifest[name] = {
            "url": url,
            "revision": revision,
            "executable": executable,
            "sha256": sha(directory / executable),
        }
    Path("reports/reference-manifest.json").write_text(
        json.dumps(manifest, indent=2), encoding="utf-8"
    )


if __name__ == "__main__":
    main()
