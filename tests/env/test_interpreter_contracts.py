"""Contracts exercised against the installed official interpreter."""

from kaggle_environments import make
from kaggle_environments.envs.kaggriculture import kaggriculture as game


def test_inputs_and_hires_are_available_only_next_turn():
    env = make("kaggriculture", configuration={"seed": 0})
    env.reset(2)
    env.step(
        [
            {
                "farmer": ["PLANT", "WHEAT"],
                "hands": [["WEST"]],
                "market": [["BUY_SEED", "WHEAT", 1], ["HIRE"]],
            },
            {},
        ]
    )
    obs = env.state[0].observation
    assert obs.private.seeds["WHEAT"] == 1
    assert len(obs.farms[0].hands) == 1
    x, y = obs.farms[0].farmer
    assert obs.farms[0].tiles[y][x] is None


def test_excess_seed_demand_cancels_all_planting():
    env = make("kaggriculture", configuration={"seed": 0})
    env.reset(2)
    obs = env.state[0].observation
    obs.private.seeds["WHEAT"] = 1
    obs.farms[0].hands = [[3, 4]]
    obs.private.inventories.append({})
    env.step([{"farmer": ["PLANT", "WHEAT"], "hands": [["PLANT", "WHEAT"]]}, {}])
    assert env.state[0].observation.private.seeds["WHEAT"] == 1
    assert env.state[0].observation.farms[0].tiles[4][3] is None


def test_ongoing_fertilizer_needs_water_and_has_four_productions():
    totals = []
    for watered in (False, True):
        farm = game._new_farm(10, 3000)
        plant = game._new_plant("STRAWBERRY", 0, 24)
        farm["tiles"][0][0] = plant
        total = 0
        for day in range(18):
            plant["watered_today"] = watered or day % 2 == 0
            plant["fertilized_until_day"] = day + 2
            game._daily_refresh_plants(farm, day, 24)
            total += plant["yield_units"]
            plant["yield_units"] = 0
        totals.append(total)
    assert totals == [4, 8]  # all four production eves are odd days


def test_animal_capacity_is_product_capacity_and_care_is_delayed():
    farm = game._new_farm(10, 3000)
    animal = game._new_animal("COW", 0)
    farm["tiles"][0][0] = animal
    for day in range(8):
        animal["fed_today"] = animal["cared_today"] = True
        game._daily_refresh_animals(farm, day)
    assert animal["yield_units"] == 6
    assert animal["pending_care_bonus"] == 1
    assert animal["animal"] == "COW"


def test_terminal_action_is_step_718_without_final_daily_drop():
    env = make("kaggriculture", configuration={"seed": 0})
    env.run(["pass", "pass"])
    assert len(env.steps) == 720
    assert env.steps[-1][0].observation.hour == 23
    assert env.steps[-1][0].observation.day == 29


def test_shed_overflow_discards_carried_items():
    private = game._new_private()
    private["shed"] = {"WHEAT": 99}
    private["inventories"] = [{"MILK": 3}]
    game._drop_inventories_to_shed(private, 100)
    assert private["shed"]["MILK"] == 1
    assert private["inventories"] == [{}]
