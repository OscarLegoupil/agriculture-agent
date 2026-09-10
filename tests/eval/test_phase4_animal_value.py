"""Official cohort transitions and same-turn purchase prerequisites."""

import pytest
from scripts.phase4_animal_value import cohort_plan


@pytest.mark.parametrize("animal", ["COW", "SHEEP", "GOOSE"])
@pytest.mark.parametrize("placed", [0, 9, 21, 25])
def test_complete_cohort_calendar_matches_official_ideal_service(animal, placed):
    from kaggle_environments.envs.kaggriculture import kaggriculture as game

    data = game.ANIMALS[animal]
    spec = (data["cost"], data["first_yield_day"], data["interval"], data["max_held"], "", "")
    plan = cohort_plan(placed, spec)
    farm = {"tiles": [[game._new_animal(animal, placed)]]}
    observed = []
    for day in range(placed, 29):
        tile = farm["tiles"][0][0]
        if "animal" not in tile:
            break
        tile["fed_today"] = day in plan["feed_days"]
        tile["cared_today"] = day in plan["care_days"]
        game._daily_refresh_animals(farm, day)
        tile = farm["tiles"][0][0]
        if tile.get("yield_units", 0):
            observed.append(
                {"production_day": day + 1, "sale_day": day + 1, "units": tile["yield_units"]}
            )
            tile["yield_units"] = 0
    assert observed == plan["events"]
    # The original event count already embeds next-day placement and day29 sale.
    purchase_day = placed - 1
    old_events = max(0, 1 + (28 - purchase_day - data["first_yield_day"]) // data["interval"])
    assert len(plan["events"]) == old_events


def test_purchase_cannot_supply_same_action_but_can_place_same_day():
    from kaggle_environments import make

    env = make("kaggriculture", configuration={"seed": 0}, debug=True)
    env.reset(2)
    passive = {"farmer": ["PASS"], "market": []}
    env.step([{"farmer": ["PICKUP", "SHEEP", 1], "market": [["BUY_ANIMAL", "SHEEP", 1]]}, passive])
    private = env.state[0].observation.private
    assert private["inventories"][0].get("SHEEP", 0) == 0
    assert private["shed"]["SHEEP"] == 1
    for action in (["PICKUP", "SHEEP", 1], ["BUILD_PASTURE"], ["PLACE", "SHEEP"]):
        env.step([{"farmer": action, "market": []}, passive])
    farm = env.state[0].observation.farms[0]
    x, y = farm["farmer"]
    assert farm["tiles"][y][x]["animal"] == "SHEEP"
    assert farm["tiles"][y][x]["placed_day"] == 0
