from kaggle_environments.envs.kaggriculture import kaggriculture as game

from kaggriculture.planning.allocator import allocate
from kaggriculture.planning.crop_roi import finite_crop_net


def test_one_day_allocator_cannot_credit_immature_crops():
    plan = allocate(tiles=4, horizon_days=1)
    assert plan.fill_crop_revenue == 0


def test_commercial_wheat_can_win_crop_allocation():
    plan = allocate(
        tiles=4,
        horizon_days=5,
        price_map={"WHEAT": 500},
        max_animals_per_species={"GOOSE": 0, "COW": 0, "SHEEP": 0},
    )
    assert plan.fill_crop == "WHEAT"


def test_single_cohort_receipts_match_interpreter():
    for crop in game.CROPS:
        spec = game.CROPS[crop]
        first = spec["first_yield_day"]
        farm = game._new_farm(10, 3000)
        private = game._new_private()
        farm["farmer"] = [4, 4]
        farm["tiles"][4][4] = game._new_plant(crop, 0, 24)
        for day in range(first + 1):
            game._apply_unit_action(farm, private, 0, ["WATER"], 10, day, 24)
            if day < first:
                game._daily_refresh_plants(farm, day, 24)
        game._apply_unit_action(farm, private, 0, ["HARVEST"], 10, first, 24)
        units = private["inventories"][0][crop]
        assert finite_crop_net(crop, first + 1, price=100) == units * 100 - spec["seed"]
