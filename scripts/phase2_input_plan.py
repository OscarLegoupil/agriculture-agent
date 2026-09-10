"""Couple fertilizer purchases and sales to the same executable task demand."""

import argparse
import hashlib
import json
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

from benchmark import episode, provenance, snapshot
from phase2_correctness import build as correctness
from phase2_logistics import INCUMBENT, replace


def build(name):
    source = correctness("accounting" if name == "compact" else "liquidity_model_expand")
    begin = source.index("    # Sell before buying.")
    end = source.index("    # Demand forecasts use")
    sales = source[begin:end]
    source = source[:begin] + source[end:]
    sales = sales.replace(" and cash >= 1000:", ":")
    sales = replace(sales, "min(12, len(plants) // 2)", "fert_tasks")
    sales = sales.replace("market.append", "sales.append")
    sales = "    sales = []\n" + sales + "    market = sales + market\n\n"
    source = replace(
        source,
        'max(0, min(12, fert_tasks) - stock["FERTILIZER"])',
        'max(0, fert_tasks - stock["FERTILIZER"])',
    )
    source = replace(
        source,
        "    if need_fert and cash > need_fert * (fert_price + 1) + 200 and fert_price < 100:",
        "    need_fert = min(need_fert, max(0, int((cash - 200) // (fert_price + 1))))\n    if need_fert and cash > need_fert * (fert_price + 1) + 200 and fert_price < 100:",
    )
    source = replace(source, "    actions: list[list[Any]]", sales + "    actions: list[list[Any]]")
    assert name in ("compact", "expanded")
    compile(source, "input_plan.py", "exec")
    return source


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--names", nargs="+", default=["compact", "expanded"])
    parser.add_argument("--seeds", nargs="+", type=int, default=[17, 103])
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--output", type=Path, default=Path("data/raw/phase2-input-plan.json"))
    args = parser.parse_args()
    opponents = [f"data/raw/reference-{name}/main.py" for name in ("seyam", "cok")]
    manifest = {
        **provenance([str(INCUMBENT), *opponents]),
        "hypothesis": "Use one funded task-demand target for input purchases and sales",
        "candidates": {},
        "episodes": [],
    }
    tasks = []
    for name in args.names:
        content = build(name).encode()
        digest = hashlib.sha256(content).hexdigest()
        path = Path("data/interim/phase2-input-plan") / name / digest / "main.py"
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


if __name__ == "__main__":
    main()
