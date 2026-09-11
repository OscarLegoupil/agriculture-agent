"""Run a declared multi-candidate panel with frozen sources and complete provenance."""

import hashlib
import json
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

from benchmark import episode, provenance, snapshot, verify_bundles


def screen(candidates, opponents, seeds, output, workers=4, inputs=(), replays=None):
    from kaggle_environments.agent import get_last_callable

    output = Path(output)
    assert candidates and opponents and seeds
    assert len(seeds) == len(set(seeds)) and len(opponents) == len(set(opponents))
    manifest = {
        **provenance([*opponents, *inputs]),
        "declared_panel": {"seeds": seeds, "seats": [0, 1], "opponents": opponents},
        "candidates": {},
        "episodes": [],
        "complete": False,
    }
    tasks = []
    for name, source in candidates.items():
        namespace = {}
        exec(source, namespace)
        loaded = get_last_callable(source)
        intended = namespace.get("agent")
        if intended is None or loaded.__code__.co_code != intended.__code__.co_code:
            raise ValueError(f"Official loader selects a different candidate policy: {name}")
        content = source.encode("utf-8")
        digest = hashlib.sha256(content).hexdigest()
        path = Path("data/interim/strategy-screen") / digest / "main.py"
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.exists():
            assert path.read_bytes() == content
        else:
            path.write_bytes(content)
        assert str(path) not in manifest["candidates"], "Duplicate candidate behavior bytes"
        manifest["candidates"][str(path)] = {
            "name": name,
            "sha256": digest,
            "snapshot": snapshot(path),
        }
        tasks.extend(
            (str(path), opponent, seed, seat, replays)
            for opponent in opponents
            for seed in seeds
            for seat in (0, 1)
        )
    output.parent.mkdir(parents=True, exist_ok=True)
    assert not output.exists(), f"Use a new experiment path rather than overwrite {output}"
    output.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    with ProcessPoolExecutor(max_workers=workers) as pool:
        for row in pool.map(episode, tasks):
            manifest["episodes"].append(row)
            output.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
            print(
                manifest["candidates"][row["candidate"]]["name"],
                row["opponent"],
                row["seed"],
                row["seat"],
                row["cash"],
                row["opponent_cash"],
                flush=True,
            )
    expected = {task[:4] for task in tasks}
    observed = {(r["candidate"], r["opponent"], r["seed"], r["seat"]) for r in manifest["episodes"]}
    assert expected == observed and len(manifest["episodes"]) == len(tasks)
    for path, metadata in manifest["candidates"].items():
        assert hashlib.sha256(Path(path).read_bytes()).hexdigest() == metadata["sha256"]
    for opponent in opponents:
        assert (
            hashlib.sha256(Path(opponent).read_bytes()).hexdigest() == manifest["hashes"][opponent]
        )
    verify_bundles(manifest)
    manifest["complete"] = True
    output.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return manifest
