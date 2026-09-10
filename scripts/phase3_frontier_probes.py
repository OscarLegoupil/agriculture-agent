"""Verify selective delivery and input batch capacity in the official interpreter.

Crop fertilizer contracts live in tests/test_phase3_contracts.py.
"""

import argparse
import hashlib
import json
from importlib.metadata import version
from pathlib import Path

from kaggle_environments.envs.kaggriculture import kaggriculture as game


def probes():
    results = {}
    for operation in (["PLACE", "MILK", 3], ["DROP"]):
        farm, private = game._new_farm(10, 3000), game._new_private()
        farm["farmer"] = [4, 4]
        private["inventories"][0] = {"WHEAT": 6, "MILK": 3, "FERTILIZER": 4}
        game._apply_unit_action(farm, private, 0, operation, 10, 4, 24)
        results[operation[0]] = {"shed": private["shed"], "inventory": private["inventories"][0]}
    farm, private = game._new_farm(10, 3000), game._new_private()
    farm["farmer"] = [4, 4]
    private["shed"] = {"WHEAT": 6, "FERTILIZER": 8}
    game._apply_unit_action(farm, private, 0, ["PICKUP", "WHEAT", 6], 10, 4, 24)
    game._apply_unit_action(farm, private, 0, ["PICKUP", "FERTILIZER", 8], 10, 4, 24)
    results["batch_pickup"] = private["inventories"][0]
    assert results["PLACE"]["inventory"] == {"WHEAT": 6, "FERTILIZER": 4}
    assert results["PLACE"]["shed"]["MILK"] == 3
    assert results["DROP"]["inventory"] == {}
    assert results["DROP"]["shed"]["WHEAT"] == 6
    assert results["batch_pickup"] == {"WHEAT": 6, "FERTILIZER": 8}
    return results


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output", type=Path, default=Path("reports/results/phase3-frontier-probes.json")
    )
    args = parser.parse_args()
    result = {
        "environment_version": version("kaggle-environments"),
        "interpreter_sha256": hashlib.sha256(Path(game.__file__).read_bytes()).hexdigest(),
        "results": probes(),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(args.output)


if __name__ == "__main__":
    main()
