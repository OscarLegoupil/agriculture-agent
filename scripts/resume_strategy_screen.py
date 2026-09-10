"""Resume an interrupted frozen strategy-screen manifest without rerunning games."""

import argparse
import hashlib
import json
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

from benchmark import episode


def resume(path: Path, workers: int, replays: str | None = None) -> dict:
    """Run only absent candidate/opponent/seed/seat episodes after verification."""
    manifest = json.loads(path.read_bytes())
    assert manifest.get("complete") is False, "The manifest is already complete"
    assert 1 <= workers <= 4
    panel = manifest["declared_panel"]
    candidates = manifest["candidates"]
    assert candidates and panel["opponents"] and panel["seeds"]
    for candidate, metadata in candidates.items():
        assert hashlib.sha256(Path(candidate).read_bytes()).hexdigest() == metadata["sha256"]
    for opponent in panel["opponents"]:
        assert hashlib.sha256(Path(opponent).read_bytes()).hexdigest() == manifest["hashes"][opponent]
    expected = {
        (candidate, opponent, seed, seat)
        for candidate in candidates
        for opponent in panel["opponents"]
        for seed in panel["seeds"]
        for seat in panel["seats"]
    }
    seen = {(row["candidate"], row["opponent"], row["seed"], row["seat"]) for row in manifest["episodes"]}
    assert seen <= expected and len(seen) == len(manifest["episodes"]), "Duplicate or foreign episode"
    tasks = [(*task, replays) for task in sorted(expected - seen)]
    assert tasks, "No missing episodes"
    with ProcessPoolExecutor(max_workers=workers) as pool:
        for row in pool.map(episode, tasks):
            manifest["episodes"].append(row)
            path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
            print(row["opponent"], row["seed"], row["seat"], row["cash"], row["opponent_cash"], flush=True)
    observed = {(row["candidate"], row["opponent"], row["seed"], row["seat"]) for row in manifest["episodes"]}
    assert observed == expected and len(observed) == len(manifest["episodes"])
    manifest["complete"] = True
    path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--replays")
    args = parser.parse_args()
    resume(args.manifest, args.workers, args.replays)


if __name__ == "__main__":
    main()
