"""Ablate animal profit-per-capital versus absolute profit per scarce herd slot."""

import argparse
import gzip
import hashlib
import json
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

from benchmark import episode, provenance, snapshot
from phase2_logistics import replace

BASES = {
    "capacity_net": "521467d45a0e2739d634ec628009753fe8e3844633bdc6e6f733f45521489a59",
    "scenario_net": "6750ea481374fb52393a1f941c9d3b4b7fc54d33d6ab46a0351d7dfb75602ba5",
}


def build(name):
    digest = BASES[name]
    raw = gzip.decompress((Path("reports/sources") / (digest + ".py.gz")).read_bytes())
    assert hashlib.sha256(raw).hexdigest() == digest
    source = raw.decode()
    old = "options.append((net / cost, animal))"
    new = "options.append((net, animal))"
    changed = replace(source, old, new)
    assert changed.replace(new, old) == source
    compile(changed, name, "exec")
    return changed


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workers", type=int, default=3)
    parser.add_argument("--output", type=Path, default=Path("data/raw/phase3-objective.json"))
    args = parser.parse_args()
    opponents = [f"data/raw/reference-{name}/main.py" for name in ("seyam", "cok")]
    manifest = {
        **provenance([*opponents, __file__]),
        "hypothesis": "Under the same affordability guard and eighteen-slot capacity, absolute net cash may allocate slots better than profit per animal purchase cost",
        "seeds": [2000, 2003, 2009, 2013],
        "candidates": {},
        "episodes": [],
        "complete": False,
    }
    tasks = []
    for name, base in BASES.items():
        content = build(name).encode()
        digest = hashlib.sha256(content).hexdigest()
        path = Path("data/interim/phase3-objective") / name / digest / "main.py"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
        manifest["candidates"][str(path)] = {
            "name": name,
            "sha256": digest,
            "base_sha256": base,
            "snapshot": snapshot(path),
        }
        tasks.extend(
            (str(path), opponent, seed, seat, None)
            for opponent in opponents
            for seed in manifest["seeds"]
            for seat in (0, 1)
        )
    with ProcessPoolExecutor(max_workers=args.workers) as pool:
        for row in pool.map(episode, tasks):
            manifest["episodes"].append(row)
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
            print(
                manifest["candidates"][row["candidate"]]["name"],
                row["opponent"],
                row["seed"],
                row["seat"],
                row["cash"] - row["opponent_cash"],
                flush=True,
            )
    assert len(manifest["episodes"]) == len(tasks)
    assert len(
        {(e["candidate"], e["opponent"], e["seed"], e["seat"]) for e in manifest["episodes"]}
    ) == len(tasks)
    for path, metadata in manifest["candidates"].items():
        assert hashlib.sha256(Path(path).read_bytes()).hexdigest() == metadata["sha256"]
    manifest["complete"] = True
    args.output.write_text(json.dumps(manifest, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
