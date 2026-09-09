"""Official transitions behind fertilizer timing and marginal-yield decisions."""

import pytest
from kaggle_environments import make
from kaggle_environments.envs.kaggriculture import kaggriculture as game


def crop_at_shed(crop):
    farm = game._new_farm(10, 3000)
    private = game._new_private()
    farm["farmer"] = [4, 4]
    plant = game._new_plant(crop, 0, 24)
    farm["tiles"][4][4] = plant
    private["inventories"][0] = {"FERTILIZER": 1}
    return farm, private, plant


@pytest.mark.parametrize("crop,age", [("WHEAT", 2), ("CARROT", 2), ("MELON", 6)])
def test_one_shot_water_growth_requires_fertilizer_before_water(crop, age):
    yields = []
    for operations in (("WATER", "FERTILIZE"), ("FERTILIZE", "WATER")):
        farm, private, plant = crop_at_shed(crop)
        for operation in operations:
            game._apply_unit_action(farm, private, 0, [operation], 10, age, 24)
        yields.append(plant["yield_units"])
        assert private["inventories"][0].get("FERTILIZER", 0) == 0
    assert yields == [2, 3]


@pytest.mark.parametrize("operations", [("WATER", "FERTILIZE"), ("FERTILIZE", "WATER")])
def test_recurring_fertilizer_lasts_through_two_production_eves(operations):
    farm, private, plant = crop_at_shed("STRAWBERRY")
    for operation in operations:
        game._apply_unit_action(farm, private, 0, [operation], 10, 9, 24)
    assert plant["yield_units"] == 0  # Neither action directly produces ongoing fruit.
    assert plant["fertilized_until_day"] == 11
    production = []
    for day in range(9, 14):
        if day > 9:
            game._apply_unit_action(farm, private, 0, ["WATER"], 10, day, 24)
        game._daily_refresh_plants(farm, day, 24)
        if plant["yield_units"]:
            production.append((day + 1, plant["yield_units"]))
            game._apply_unit_action(farm, private, 0, ["HARVEST"], 10, day + 1, 24)
    assert production == [(10, 2), (12, 2), (14, 1)]
    assert private["inventories"][0]["STRAWBERRY"] == 5


def test_fertilizing_capped_one_shot_spends_input_without_more_yield():
    farm, private, plant = crop_at_shed("WHEAT")
    plant["yield_units"] = 6
    game._apply_unit_action(farm, private, 0, ["FERTILIZE"], 10, 4, 24)
    game._apply_unit_action(farm, private, 0, ["WATER"], 10, 4, 24)
    assert plant["yield_units"] == 6
    assert private["inventories"][0].get("FERTILIZER", 0) == 0


def test_market_fertilizer_cannot_support_same_turn_field_action():
    env = make("kaggriculture", configuration={"seed": 17})
    obs = env.reset(2)[0].observation
    obs.farms[0].tiles[4][4] = game._new_plant("STRAWBERRY", 0, 24)
    env.step([{"farmer": ["FERTILIZE"], "market": [["BUY_PRODUCT", "FERTILIZER", 1]]}, {}])
    obs = env.state[0].observation
    assert obs.private.shed["FERTILIZER"] == 1
    assert obs.farms[0].tiles[4][4]["fertilized_until_day"] < 0
    env.step([{"farmer": ["PICKUP", "FERTILIZER", 1]}, {}])
    env.step([{"farmer": ["FERTILIZE"]}, {}])
    assert env.state[0].observation.farms[0].tiles[4][4]["fertilized_until_day"] == 2
