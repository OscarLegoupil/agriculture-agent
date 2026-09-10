"""Fetch reviewed phase-two opponents without redistributing their source."""

import hashlib
import json
import subprocess
from pathlib import Path

REFERENCES = {
    "seyam": {
        "url": "https://github.com/Seyamalam/Kaggriculture.git",
        "revision": "8b8c421eb10634c756583ce10c75189f50c83a72",
        "git_blob_sha256": "0cd14b653102d276c4f902fa3b8c6bd81d869b8ab64c422cb881b9d2346ec639",
        "sha256": "4c02a323b0939e8f99df69dc6c23026946b033b0d831c79216ffac0ded9c8e60",
        "lineage": "Kaito Fukami public V18/C20 routes with recovery overlay",
    },
    "cok": {
        "url": "https://github.com/COK-ZhangZiliang/Kaggriculture.git",
        "revision": "7ef67eac458cd9ecd13786063e2e581fbe7403ec",
        "git_blob_sha256": "56831f3c43c9727d90016b7a7a8d4eb51d1a4c08c1120d58f061d9176e8bc109",
        "sha256": "1c7335f698692f1c7bac34913a9ededc0f736dfb2b51346a4fa59098ab471d01",
        "lineage": "Adaptive Farming Strategy public routes with recovery controller",
    },
}


def main():
    manifest = {"reviewed_on": "2026-09-09", "references": {}}
    for name, reference in REFERENCES.items():
        directory = Path("data/raw") / f"reference-{name}"
        if not directory.exists():
            subprocess.run(["git", "clone", reference["url"], str(directory)], check=True)
        current = subprocess.check_output(
            ["git", "-C", str(directory), "rev-parse", "HEAD"], text=True
        ).strip()
        if current != reference["revision"]:
            dirty = subprocess.check_output(
                ["git", "-C", str(directory), "status", "--porcelain"], text=True
            )
            if dirty:
                raise RuntimeError(f"Reference checkout has local changes: {directory}")
            subprocess.run(
                ["git", "-C", str(directory), "fetch", "origin", reference["revision"]],
                check=True,
            )
            subprocess.run(
                ["git", "-C", str(directory), "checkout", "--detach", reference["revision"]],
                check=True,
            )
        blob = subprocess.check_output(["git", "-C", str(directory), "show", "HEAD:main.py"])
        if hashlib.sha256(blob).hexdigest() != reference["git_blob_sha256"]:
            raise RuntimeError(f"Unexpected reference blob: {directory}")
        # The qualification panel used Windows checkouts. Preserve those exact
        # bytes on every platform instead of silently changing executable hashes.
        executable = blob.replace(b"\r\n", b"\n").replace(b"\n", b"\r\n")
        if hashlib.sha256(executable).hexdigest() != reference["sha256"]:
            raise RuntimeError(f"Unexpected reference executable: {directory}")
        target = directory / "main.py"
        if target.exists() and target.read_bytes() not in (blob, executable):
            raise RuntimeError(f"Reference executable has local changes: {target}")
        target.write_bytes(executable)
        manifest["references"][name] = {
            **reference,
            "executable": str(target).replace("\\", "/"),
            "newline": "CRLF, matching qualification executable",
            "license": "Apache-2.0 attributed portions; notices retained in clone",
        }
    Path("reports/challenge-reference-manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
    )


if __name__ == "__main__":
    main()
