"""Terminal annual calendars are checked against official crop transitions."""

from copy import deepcopy

import pytest
from experiments.terminal_crops import (
    annual_contracts,
    build,
    official_probe,
    terminal_choices,
    terminal_rotation,
)
from kaggle_environments import make
from kaggle_environments.agent import get_last_callable
from kaggle_environments.envs.kaggriculture import kaggriculture as game


def execute_contract(contract):
    farm, private = game._new_farm(10, 3000), game._new_private()
    farm["farmer"] = [4, 4]
    crop = contract["crop"]
    private["seeds"][crop] = 1
    private["shed"]["FERTILIZER"] = 1
    calendar = dict(contract["calendar"])
    for day in range(contract["planted_day"], contract["harvest_day"] + 1):
        for op in calendar.get(day, ()):
            action = (
                ["PLANT", crop]
                if op == "PLANT"
                else ["PICKUP", "FERTILIZER", 1]
                if op == "PICKUP_FERTILIZER"
                else [op]
            )
            game._apply_unit_action(farm, private, 0, action, 10, day, 24, 100)
        game._daily_refresh_plants(farm, day, 24)
        game._decay_plants(farm, (day + 1) * 24)
        game._drop_inventories_to_shed(private, 100)
    return farm, private


@pytest.mark.parametrize("crop,unfertilized,fertilized", [("WHEAT", 4, 6), ("CARROT", 3, 4)])
def test_calendar_units_and_prerequisites_match_official_interpreter(
    crop, unfertilized, fertilized
):
    for use_fertilizer, maximum in ((False, unfertilized), (True, fertilized)):
        contracts = annual_contracts(crop, 20, 0, 0, 0, use_fertilizer)
        assert max(contract["units"] for contract in contracts) == maximum
        for contract in contracts:
            farm, private = execute_contract(contract)
            assert private["shed"].get(crop, 0) == contract["units"]
            assert farm["tiles"][4][4] is None
            assert contract["calendar"][0][1] == ("PLANT", "WATER")


def test_terminal_contract_truncates_wheat_growth_and_charges_same_day_delivery():
    contracts = annual_contracts("WHEAT", 27, 0, 0, 2)
    assert contracts and max(contract["units"] for contract in contracts) == 2
    assert all(contract["sale_day"] == 29 for contract in contracts)
    assert all(contract["calendar"][-1][1][-2:] == ("HARVEST", "DROP") for contract in contracts)
    assert annual_contracts("CARROT", 28, 0, 0, 0) == []
    assert annual_contracts("CARROT", 27, 23, 0, 0) == []
    assert annual_contracts("CARROT", 27, 0, 0, 11) == []


def test_rotation_selects_observable_demand_and_rejects_unprofitable_planting():
    quotes = {
        crop: {day: price for day in range(18, 30)}
        for crop, price in (("WHEAT", 40), ("CARROT", 35))
    }
    ordinary = terminal_rotation(22, 0, 0, 0, quotes)
    assert ordinary["crop"] == "WHEAT"
    quotes["CARROT"] = dict.fromkeys(range(18, 30), 120)
    carrot = terminal_rotation(22, 0, 0, 0, quotes)
    assert carrot["crop"] == "CARROT"
    assert len(carrot["sequence"]) == 2
    depressed = {crop: dict.fromkeys(range(18, 30), 1) for crop in quotes}
    assert terminal_rotation(22, 0, 0, 0, depressed)["sequence"] == ()


def state():
    env = make("kaggriculture", configuration={"seed": 0})
    env.reset()
    obs = deepcopy(env.state[0].observation)
    obs.update(day=22, hour=0, step=528, player=0)
    farm = game._new_farm(10, 5000)
    farm["farmer"] = [4, 4]
    obs["farms"][0] = farm
    obs["private"] = game._new_private()
    obs["private"]["seeds"] = {"CARROT": 4}
    prices = obs["market"]["prices"]
    prices.update(CARROT=120, WHEAT=35, STRAWBERRY=1)
    traces = {crop: [price] * 7 for crop, price in prices.items()}
    access = [(4, 4), (4, 5), (5, 4), (5, 5)]
    return obs, dict(env.configuration), traces, access


def test_replacement_preserves_held_yield_and_valuable_existing_crop():
    obs, _, traces, access = state()
    target = (4, 3)
    plant = game._new_plant("STRAWBERRY", 10, 24)
    plant.update(yield_units=1)
    obs["farms"][0]["tiles"][3][4] = plant
    assert target not in terminal_choices(obs, [(4, 4)], access, traces)
    plant["yield_units"] = 0
    choice = terminal_choices(obs, [(4, 4)], access, traces)
    assert choice[target]["crop"] == "CARROT"
    obs["market"]["prices"]["STRAWBERRY"] = 500
    traces["STRAWBERRY"] = [500] * 7
    assert target not in terminal_choices(obs, [(4, 4)], access, traces)


def test_packaged_policy_executes_replacement():
    obs, cfg, _, _ = state()
    obs["farms"][0]["tiles"][4][4] = game._new_plant("STRAWBERRY", 0, 24)
    # Remove irrelevant free land so that an actual replacement is required.
    for row in obs["farms"][0]["tiles"]:
        for x, tile in enumerate(row):
            if tile is None:
                row[x] = "LOCKED"
    ns = {}
    exec(build(), ns)
    assert get_last_callable(build()).__name__ == "agent"
    first = ns["agent"](deepcopy(obs), cfg)
    assert first["farmer"] == ["DIG"]
    game._apply_unit_action(obs["farms"][0], obs["private"], 0, first["farmer"], 10, 22, 24, 100)
    obs.update(hour=1, step=529)
    second = ns["agent"](deepcopy(obs), cfg)
    assert second["farmer"] == ["PLANT", "CARROT"]
    game._apply_unit_action(obs["farms"][0], obs["private"], 0, second["farmer"], 10, 22, 24, 100)
    obs.update(hour=2, step=530)
    assert ns["agent"](deepcopy(obs), cfg)["farmer"] == ["WATER"]


def test_full_interpreter_cash_flow_includes_input_execution_and_actual_sale():
    rows = official_probe()
    assert all(row["units_expected"] == row["units_delivered"] for row in rows)
    for crop in ("WHEAT", "CARROT"):
        unfertilized, fertilized = [row for row in rows if row["crop"] == crop]
        assert fertilized["worker_actions"] == unfertilized["worker_actions"] + 2
        assert unfertilized["net_cash"] > fertilized["net_cash"]
        assert unfertilized["net_after_action_charge"] > 0
