"""Defer flexible herd allocation until two town-shop observations exist."""

import argparse
import hashlib
import json
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

from benchmark import episode, provenance, snapshot
from phase2_adaptive_herd import build as adaptive
from phase2_logistics import replace


def build(base):
    source = adaptive(base, 18)
    return replace(
        source,
        "desired = dict(COW=14, SHEEP=14, GOOSE=14)",
        'desired = (dict(COW=14, SHEEP=14, GOOSE=14) if len(obs["town"]["unlocked_shops"]) >= 2 else dict(COW=p["cows"], SHEEP=p["sheep"], GOOSE=p["geese"]))',
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workers", type=int, default=2)
    args = parser.parse_args()
    base = Path(Path("data/raw/phase2-best-path.txt").read_text().strip())
    assert (
        hashlib.sha256(base.read_bytes()).hexdigest()
        == "0098d9e4f77e2420cb4a09abd47e49f5160009cd0818ae37a793bc3e419ffc4b"
    )
    content = build(base).encode()
    digest = hashlib.sha256(content).hexdigest()
    target = Path("data/interim/phase2-economics/deferred-herd") / digest / "main.py"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(content)
    opponents = ["data/raw/reference-seyam/main.py", "data/raw/reference-cok/main.py"]
    manifest = {
        **provenance([str(base), *opponents]),
        "base": str(base),
        "candidate": str(target),
        "sha256": digest,
        "snapshot": snapshot(target),
        "hypothesis": "Preserve mixed species limits until two shops are observable; no forecast of their realized identities",
        "episodes": [],
    }
    tasks = [
        (str(target), opponent, seed, seat, None)
        for opponent in opponents
        for seed in (17, 103)
        for seat in (0, 1)
    ]
    output = Path("data/interim/phase2-economics/deferred-herd-results.json")
    with ProcessPoolExecutor(max_workers=args.workers) as pool:
        for row in pool.map(episode, tasks):
            manifest["episodes"].append(row)
            output.write_text(json.dumps(manifest, indent=2))
            print(
                row["opponent"],
                row["seed"],
                row["seat"],
                row["cash"] - row["opponent_cash"],
                flush=True,
            )


if __name__ == "__main__":
    main()
