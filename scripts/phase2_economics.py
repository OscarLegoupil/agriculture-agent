"""Interpreter-backed diagnostics of v7's finite-season economic approximations.

These ideal servicing probes are upper bounds, not deployable performance.
Run with: uv run python scripts/phase2_economics.py
"""

from __future__ import annotations

import json

from kaggle_environments.envs.kaggriculture import kaggriculture as game


def care_probe(animal: str, capped: bool, production_exception: bool = False) -> dict:
    farm = game._new_farm(10, 3000)
    tile = game._new_animal(animal, 0)
    farm["tiles"][0][0] = tile
    spec = game.ANIMALS[animal]
    actions = output = 0
    for day in range(29):
        tile["fed_today"] = True
        production_age = day + 1 - spec["first_yield_day"]
        production_eve = production_age >= 0 and production_age % spec["interval"] == 0
        care = (
            not capped
            or tile.get("pending_care_bonus", 0) < spec["max_held"] - 1
            or (production_exception and production_eve)
        )
        tile["cared_today"] = care
        actions += care
        game._daily_refresh_animals(farm, day)
        output += tile["yield_units"]
        tile["yield_units"] = 0  # ideal immediate harvesting; no travel model
    return {"care_actions": actions, "product_units": output}


def crop_probe(crop: str) -> dict:
    farm = game._new_farm(10, 3000)
    tile = game._new_plant(crop, 0, 24)
    farm["tiles"][0][0] = tile
    private = game._new_private()
    private["inventories"][0] = {"FERTILIZER": 10}
    farm["farmer"] = [0, 0]
    spec = game.CROPS[crop]
    applications = 0
    total = 0
    for day in range(20):
        if spec["ongoing"]:
            eve = day + 1 - spec["first_yield_day"]
            growth = eve >= 0 and eve % spec["interval"] == 0 and eve // spec["interval"] < 4
        else:
            growth = (spec["max_yield_day"] + 1) // 2 <= day <= spec["max_yield_day"]
        if (
            growth
            and tile["fertilized_until_day"] < day
            and tile["yield_units"] < spec["max_yield"]
        ):
            game._apply_unit_action(farm, private, 0, ["FERTILIZE"], 10, day, 24)
            applications += 1
        # Production transitions come from the official interpreter. For
        # one-shot crops WATER has immediate growth, unlike ongoing EOD growth.
        game._apply_unit_action(farm, private, 0, ["WATER"], 10, day, 24)
        if (
            not spec["ongoing"]
            and day >= spec["first_yield_day"]
            and tile["yield_units"] == spec["max_yield"]
        ):
            return {
                "harvest_day": day,
                "product_units": tile["yield_units"],
                "fertilizer_units": applications,
            }
        game._daily_refresh_plants(farm, day, 24)
        if spec["ongoing"]:
            total += tile["yield_units"]
            tile["yield_units"] = 0
            if day + 1 >= spec["first_yield_day"] + 3 * spec["interval"]:
                return {
                    "harvest_day": day + 1,
                    "product_units": total,
                    "fertilizer_units": applications,
                }
    raise AssertionError(crop)


def main() -> None:
    print(
        json.dumps(
            {
                "scope": "ideal servicing diagnostics; no future randomness; not a policy benchmark",
                "care": {
                    a: {
                        "daily": care_probe(a, False),
                        "naive_bank_cap": care_probe(a, True),
                        "production_aware_cap": care_probe(a, True, True),
                    }
                    for a in game.ANIMALS
                },
                "crops": {c: crop_probe(c) for c in ("TOMATO", "STRAWBERRY", "MELON")},
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
