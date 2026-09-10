"""Value manure collection and animal co-products against the difficult field."""

import argparse
import hashlib
import json
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

from benchmark import episode, provenance, snapshot
from phase2_logistics import replace
from phase3_startup import build as opening


def build(name):
    assert name in ("priced_collection", "coproduct_investment")
    source = opening("startup_fert_reserve10")
    source = replace(
        source,
        '"COLLECT_FERTILIZER", 18 if fert_price < 20 else 40',
        '"COLLECT_FERTILIZER", max(1, fert_price)',
    )
    if name == "coproduct_investment":
        source = replace(
            source,
            "projected, _ = forecast_inventory(obs, CROPS, ANIMALS, SHOPS)",
            "projected, price_paths = forecast_inventory(obs, CROPS, ANIMALS, SHOPS)",
        )
        source = replace(
            source,
            "PARAMS.update(cows=10, sheep=4, geese=0, hands=12)",
            "PARAMS.update(cows=10, sheep=6, geese=0, hands=12)",
        )
        source = replace(
            source,
            "            net = revenue - cost - feed_cost - (29 - day) * 12",
            """            # Daily manure starts before the animal's main product matures.
            # A 70% collection scenario charges transport/work below and reduces
            # subsequent marginal sale prices for the prospective extra supply.
            coproduct = sum(0.7 * max(1, min(fert_price, price) - 0.2 * 0.7 * (offset + 1))
                            for offset, price in enumerate(price_paths["FERTILIZER"][1:]))
            net = revenue + coproduct - cost - feed_cost - (29 - day) * 16""",
        )
    compile(source, name, "exec")
    return source


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--names", nargs="+", default=["priced_collection", "coproduct_investment"])
    parser.add_argument("--seeds", nargs="+", type=int, default=[2000, 2003, 2009, 2013])
    parser.add_argument("--workers", type=int, default=3)
    parser.add_argument("--output", type=Path, default=Path("data/raw/phase3-manure.json"))
    args = parser.parse_args()
    opponents = [f"data/raw/reference-{name}/main.py" for name in ("seyam", "cok")]
    manifest = {
        **provenance([*opponents, __file__, "scripts/phase3_startup.py"]),
        "hypothesis": "Manure opportunity value changes servicing and funded herd selection",
        "candidates": {},
        "episodes": [],
        "complete": False,
    }
    tasks = []
    for name in args.names:
        content = build(name).encode("utf-8")
        digest = hashlib.sha256(content).hexdigest()
        path = Path("data/interim/phase3-manure") / name / digest / "main.py"
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
            for seed in args.seeds
            for seat in (0, 1)
        )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with ProcessPoolExecutor(max_workers=args.workers) as pool:
        for row in pool.map(episode, tasks):
            manifest["episodes"].append(row)
            args.output.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
            print(
                manifest["candidates"][row["candidate"]]["name"],
                row["opponent"],
                row["seed"],
                row["seat"],
                row["cash"],
                row["opponent_cash"],
                flush=True,
            )
    for path, metadata in manifest["candidates"].items():
        assert hashlib.sha256(Path(path).read_bytes()).hexdigest() == metadata["sha256"]
    manifest["complete"] = True
    args.output.write_text(json.dumps(manifest, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
