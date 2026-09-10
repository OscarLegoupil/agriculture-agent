"""Verify and summarize completed feed-cohort and production interaction panels."""

import argparse
import gzip
import hashlib
import json
import math
from collections import Counter
from pathlib import Path
from statistics import mean

try:
    from .evidence_io import read_result
    from .phase2_compare import compare_manifests
    from .phase4_compare import subset
except ImportError:
    from evidence_io import read_result
    from phase2_compare import compare_manifests
    from phase4_compare import subset


def verify_screen(manifest):
    if manifest.get("complete") is not True:
        raise ValueError("Refusing to inspect outcomes from a partial panel")
    panel = manifest["declared_panel"]
    expected = {
        (c, o, s, seat)
        for c in manifest["candidates"]
        for o in panel["opponents"]
        for s in panel["seeds"]
        for seat in panel["seats"]
    }
    actual = {(r["candidate"], r["opponent"], r["seed"], r["seat"]) for r in manifest["episodes"]}
    if expected != actual or len(expected) != len(manifest["episodes"]):
        raise ValueError("Full declared candidate/scenario coverage differs")
    for candidate, metadata in manifest["candidates"].items():
        for content in (
            Path(candidate.replace("\\", "/")).read_bytes(),
            gzip.decompress(Path(metadata["snapshot"].replace("\\", "/")).read_bytes()),
        ):
            if hashlib.sha256(content).hexdigest() != metadata["sha256"]:
                raise ValueError("Source or snapshot differs from recorded identity")


def candidate_manifest(manifest, candidate):
    metadata = manifest["candidates"][candidate]
    return {
        **manifest,
        "arguments": {"candidate": candidate},
        "executed_candidate": candidate,
        "candidate_snapshot": metadata["snapshot"],
        "hashes": {**manifest["hashes"], candidate: metadata["sha256"]},
        "episodes": [r for r in manifest["episodes"] if r["candidate"] == candidate],
    }


def behavior(rows, ratio=None, crop_capacity=50):
    compositions = [
        next(day["composition"] for day in r["daily"] if day["step"] == 360) for r in rows
    ]
    products = sorted(set().union(*compositions))
    losses = sum((Counter(r["losses"]) for r in rows), Counter())
    return {
        "games": len(rows),
        "wheat_net_cash_mean_including_seeds": mean(
            r["ledger"].get("income:WHEAT", 0) - r["ledger"].get("expense:WHEAT", 0) for r in rows
        ),
        "wheat_income_mean": mean(r["ledger"].get("income:WHEAT", 0) for r in rows),
        "wheat_expense_mean_including_seeds": mean(
            r["ledger"].get("expense:WHEAT", 0) for r in rows
        ),
        "wheat_seed_units_mean": mean(r["ledger"].get("units:BUY_SEED:WHEAT", 0) for r in rows),
        "wheat_purchased_feed_units_mean": mean(
            r["ledger"].get("units:BUY_PRODUCT:WHEAT", 0) for r in rows
        ),
        "berry_income_mean": mean(r["ledger"].get("income:STRAWBERRY", 0) for r in rows),
        "labor_expense_mean": mean(r["ledger"].get("expense:labor", 0) for r in rows),
        "successful_hires_mean": mean(r["ledger"].get("hires", 0) for r in rows),
        "moves_mean": mean(
            sum(
                r["realized_actions"].get("success:" + op, 0)
                for op in ("NORTH", "SOUTH", "EAST", "WEST")
            )
            for r in rows
        ),
        "day15_mean_composition": {
            product: mean(c.get(product, 0) for c in compositions) for product in products
        },
        "losses_total": dict(losses),
        "stderr_turns": sum(r["stderr_turns"] for r in rows),
        "max_action_seconds": max(r["runtime_max_seconds"] for r in rows),
        "daily_capacity": [
            {
                "day": day,
                "wheat_mean": mean(d["composition"].get("WHEAT", 0) for d in observations),
                "berries_mean": mean(d["composition"].get("STRAWBERRY", 0) for d in observations),
                "animals_mean": mean(d["animals"] for d in observations),
                "wheat_target_mean": mean(
                    min(28, max(7, math.ceil(d["animals"] * ratio))) for d in observations
                )
                if ratio
                else None,
                "crop_budget_headroom_mean": mean(crop_capacity - d["crops"] for d in observations),
                "nonproductive_owned_tiles_upper_bound_mean": mean(
                    25 * d["land"] - d["crops"] - d["animals"] for d in observations
                ),
                "plots_mean": mean(d["land"] for d in observations),
            }
            for day in range(8, 21)
            for observations in [
                [next(d for d in r["daily"] if d["step"] == day * 24) for r in rows]
            ]
        ],
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--incumbent",
        type=Path,
        default=Path("reports/results/phase3-validation-challenger.json.gz"),
    )
    parser.add_argument("--feed", type=Path, default=Path("data/raw/phase4-feed-mix.json"))
    parser.add_argument(
        "--interaction", type=Path, default=Path("data/raw/phase4-production-interaction.json")
    )
    parser.add_argument("--land", type=Path, default=Path("data/raw/phase4-land.json"))
    parser.add_argument(
        "--field", type=Path, help="Include a completed broader high-feed confirmation"
    )
    parser.add_argument(
        "--output", type=Path, default=Path("reports/results/phase4-feed-mix-summary.json")
    )
    args = parser.parse_args()
    incumbent = read_result(args.incumbent)
    panels = [(path, read_result(path)) for path in (args.feed, args.interaction)]
    for _, panel in panels:
        verify_screen(panel)
    land = read_result(args.land)
    # This older driver predates declared_panel. Validate the full historical
    # 48-game panel against the same explicitly declared scenarios before slicing.
    land = {**land, "declared_panel": panels[0][1]["declared_panel"]}
    verify_screen(land)
    land_path = next(path for path, meta in land["candidates"].items() if meta["mode"] == "crop70")
    land70 = candidate_manifest(land, land_path)
    report = {
        "complete": True,
        "scope": "known four-seed development panels; no additive or fresh-validation claim",
        "inputs": {
            "incumbent": {
                "path": args.incumbent.as_posix(),
                "sha256_file": hashlib.sha256(args.incumbent.read_bytes()).hexdigest(),
            }
        },
        "candidates": [],
    }
    report["inputs"]["land"] = {
        "path": args.land.as_posix(),
        "sha256_file": hashlib.sha256(args.land.read_bytes()).hexdigest(),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    for path, panel in panels:
        declared = panel["declared_panel"]
        old = subset(incumbent, declared["opponents"], declared["seeds"])
        report["inputs"][path.stem] = {
            "path": path.as_posix(),
            "sha256_file": hashlib.sha256(path.read_bytes()).hexdigest(),
        }
        for candidate, metadata in panel["candidates"].items():
            new = candidate_manifest(panel, candidate)
            comparison = compare_manifests(
                old, new, dict.fromkeys(declared["opponents"], 1 / len(declared["opponents"]))
            )
            land_comparison = (
                compare_manifests(
                    land70,
                    new,
                    dict.fromkeys(declared["opponents"], 1 / len(declared["opponents"])),
                )
                if path == args.interaction
                else None
            )
            measurement = {}
            ratio = 1.0 if "balanced" in metadata["name"] else 1.5
            capacity = 70 if metadata["name"].startswith("expanded") else 50
            for opponent in declared["opponents"]:
                measurement[opponent] = {
                    role: behavior(
                        [r for r in manifest["episodes"] if r["opponent"] == opponent],
                        ratio if role == "candidate" else None,
                        capacity if role == "candidate" else 50,
                    )
                    for role, manifest in [("incumbent", old), ("candidate", new)]
                }
            report["candidates"].append(
                {
                    "metadata": metadata,
                    "comparison": comparison,
                    "behavior": measurement,
                    "comparison_against_land70": land_comparison,
                }
            )
        name = path.name.removesuffix(".gz").removesuffix(".json")
        archive = args.output.parent / (name + ".json.gz")
        original = gzip.decompress(path.read_bytes()) if path.suffix == ".gz" else path.read_bytes()
        archive.write_bytes(gzip.compress(original, mtime=0))
    if args.field:
        field = read_result(args.field)
        if field.get("complete") is not True:
            raise ValueError("Broader confirmation is not complete")
        opponents = sorted({r["opponent"] for r in field["episodes"]})
        seeds = list(range(3000, 3032))
        old = subset(incumbent, opponents, seeds)
        comparison = compare_manifests(old, field, dict.fromkeys(opponents, 1 / len(opponents)))
        if (
            comparison["identities"]["challenger"]["sha256"]
            != "e15a78e4eed4929480c4225e74ebd3f8abb3aee38e2b459832ae8a7b2de63265"
        ):
            raise ValueError("Broader field is not the declared high-feed candidate")
        report["broader_confirmation"] = {
            "comparison": comparison,
            "behavior": {
                opponent: {
                    role: behavior(
                        [r for r in manifest["episodes"] if r["opponent"] == opponent],
                        1.5 if role == "candidate" else None,
                    )
                    for role, manifest in [("incumbent", old), ("candidate", field)]
                }
                for opponent in opponents
            },
        }
        report["inputs"]["field"] = {
            "path": args.field.as_posix(),
            "sha256_file": hashlib.sha256(args.field.read_bytes()).hexdigest(),
        }
    args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(
        json.dumps(
            [{r["metadata"]["name"]: r["comparison"]["aggregate"]} for r in report["candidates"]],
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
