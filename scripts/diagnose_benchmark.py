"""Aggregate realized execution and accounting from saved official games."""

import argparse
import json
from collections import defaultdict
from pathlib import Path
from statistics import mean

from evidence_io import read_result


def diagnose(records):
    grouped = defaultdict(list)
    for row in records:
        grouped[row["opponent"]].append(row)
    report = {}
    for opponent, games in grouped.items():
        metrics = defaultdict(list)
        for row in games:
            ledger, actions = row["ledger"], row["realized_actions"]
            income = sum(v for k, v in ledger.items() if k.startswith("income:"))
            expense = sum(v for k, v in ledger.items() if k.startswith("expense:"))
            metrics["income"].append(income)
            metrics["expense"].append(expense)
            metrics["accounting_error"].append(
                row["cash"] - row["configuration"]["startingMoney"] - income + expense
            )
            for key in ("hires", "land_purchases", "expense:labor", "expense:land"):
                metrics[key].append(ledger.get(key, 0))
            travel = sum(actions.get("success:" + d, 0) for d in ("NORTH", "SOUTH", "EAST", "WEST"))
            metrics["travel"].append(travel)
            metrics["successful_work"].append(
                sum(v for k, v in actions.items() if k.startswith("success:")) - travel
            )
            metrics["failed_work"].append(
                sum(v for k, v in actions.items() if k.startswith("failed:"))
            )
            metrics["idle"].append(actions.get("idle:PASS", 0))
            for key in (
                "water_deaths",
                "animal_escapes",
                "terminal_abandonment",
                "terminal_escapes",
                "overflow_units",
            ):
                metrics[key].append(row["losses"].get(key, 0))
            metrics["final_shed_units"].append(row["daily"][-1]["shed"])
            metrics["final_carried_units"].append(row["daily"][-1]["carried"])
            metrics["peak_productive_tiles"].append(
                max(d["crops"] + d["animals"] for d in row["daily"])
            )
        worst = min(games, key=lambda r: r["cash"] - r["opponent_cash"])
        report[opponent] = {
            "games": len(games),
            "metrics": {
                k: {"mean": mean(v), "total": sum(v), "max": max(v)} for k, v in metrics.items()
            },
            "worst_cash_gap": {
                k: worst[k]
                for k in ("seed", "seat", "cash", "opponent_cash", "losses", "replay_path")
            },
        }
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.write_text(
        json.dumps(diagnose(read_result(args.input)["episodes"]), indent=2) + "\n", encoding="utf-8"
    )
