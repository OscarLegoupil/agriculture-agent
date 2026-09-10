"""Test early berry cohorts financed by wheat before a small delayed herd."""

import argparse
import gzip
import hashlib
import json
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

from benchmark import episode, provenance, snapshot
from phase2_logistics import INCUMBENT, replace
from phase2_mixed_expansion import candidate as mixed


def candidate(name):
    source = mixed("cashbridge50")
    source = replace(
        source,
        "if day < 5:\n        desired = dict(COW=2, SHEEP=2, GOOSE=0)",
        "if day < 6:\n        desired = dict(COW=0, SHEEP=0, GOOSE=0)",
    )
    wheat = 10 if name == "berries45_mixed" else 8
    source = replace(
        source,
        '        if day < 10 and planned["WHEAT"] < 10:\n            values["WHEAT"] = max(values.values()) + 1',
        f'        if day < 14:\n            if planned["WHEAT"] < {wheat}:\n                values["WHEAT"] = max(values.values()) + 1\n            else:\n                values["STRAWBERRY"] = max(values.values()) + 1',
    )
    parameters = dict(
        cows=2,
        sheep=2,
        geese=4,
        crop_tiles=45,
        quadrants=3,
        hands=12,
        feed_grown=wheat,
        crop_bias={},
    )
    if name == "berries55_goose":
        parameters.update(cows=0, sheep=2, geese=4, crop_tiles=55)
    else:
        assert name == "berries45_mixed"
    source = replace(source, "def agent(", f"PARAMS.update({parameters!r})\n\n\ndef agent(")
    compile(source, name, "exec")
    return source


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stage", choices=("probe", "followup"), default="probe")
    parser.add_argument("--workers", type=int, default=2)
    parser.add_argument("--output", type=Path, default=Path("data/raw/phase2-preemption.json"))
    args = parser.parse_args()
    opponents = ["data/raw/reference-seyam/main.py", "data/raw/reference-cok/main.py"]
    manifest = {
        **provenance(
            [
                str(INCUMBENT),
                "scripts/phase2_preemption.py",
                "scripts/phase2_mixed_expansion.py",
                "scripts/phase2_opening.py",
                *opponents,
            ]
        ),
        "hypothesis": "An animal-free opening places berry cohorts before competitor supply, with continued wheat turnover financing service and a small herd after day6",
        "candidates": {},
        "episodes": [],
    }
    if args.stage == "followup":
        manifest = json.loads(args.output.read_text())
        assert len(manifest["episodes"]) == 4, "Inspect exactly four probe games before extending"
    done = {(e["candidate"], e["opponent"], e["seed"], e["seat"]) for e in manifest["episodes"]}
    tasks = []
    for name in ("berries45_mixed", "berries55_goose"):
        if args.stage == "followup":
            metadata = next(v for v in manifest["candidates"].values() if v["name"] == name)
            content = gzip.decompress(Path(metadata["snapshot"]).read_bytes())
            assert hashlib.sha256(content).hexdigest() == metadata["sha256"]
        else:
            content = candidate(name).encode()
        digest = hashlib.sha256(content).hexdigest()
        path = Path("data/interim/phase2-preemption") / name / digest / "main.py"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
        manifest["candidates"][str(path)] = {
            "name": name,
            "sha256": digest,
            "snapshot": snapshot(path),
        }
        tasks.extend(
            (str(path), opponent, seed, seat, None)
            for opponent in opponents
            for seed in (17, 103)
            for seat in (0, 1)
            if (args.stage != "probe" or (seed == 17 and seat == 0))
            and (str(path), opponent, seed, seat) not in done
        )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with ProcessPoolExecutor(max_workers=args.workers) as pool:
        for row in pool.map(episode, tasks):
            manifest["episodes"].append(row)
            args.output.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
            print(
                manifest["candidates"][row["candidate"]]["name"],
                row["opponent"],
                row["seed"],
                row["seat"],
                row["cash"],
                row["opponent_cash"],
                flush=True,
            )


if __name__ == "__main__":
    main()
