"""Investment finance must follow legal collection, transport and actual sales."""

import hashlib
from copy import deepcopy

import pytest
from experiments.daily_routes import build as fleet_build
from experiments.investment_liquidity import build, investment_liquidity_possible
from kaggle_environments import make
from kaggle_environments.agent import get_last_callable
from kaggle_environments.envs.kaggriculture import kaggriculture as game

ACCESS = {(4, 4), (4, 5), (5, 4), (5, 5)}


def world(seat=0):
    env = make("kaggriculture", configuration={"seed": 5001, "weedSpawnChance": 0})
    env.reset(2)
    obs = env.state[0].observation
    obs.update(step=121, day=5, hour=1)
    farm = obs.farms[seat]
    farm["money"] = 1040
    farm["hands"] = [[4, 4] for _ in range(6)]
    animal_cells = {(4, y) for y in range(1, 5)}
    index = 0
    for y, row in enumerate(farm["tiles"]):
        for x, tile in enumerate(row):
            if tile == "LOCKED":
                continue
            if (x, y) in animal_cells:
                animal = game._new_animal("SHEEP" if y < 3 else "COW", 0)
                animal["fertilizer_available"] = True
                row[x] = animal
            else:
                crop = "WHEAT" if index < 7 else "MELON"
                row[x] = game._new_plant(crop, 3 if crop == "WHEAT" else 0, 24)
                row[x]["watered_today"] = True
                index += 1
    private = env.state[seat].observation.private
    private["shed"] = {"WHEAT": 4}
    private["inventories"] = [{} for _ in range(7)]
    # Only the history length is needed by the framework's next-step counter.
    env.steps = [env.state] * 122
    return env


def view(env, seat=0):
    return env._Environment__get_shared_state(seat).observation


def inputs(obs):
    farm = obs["farms"][obs["player"]]
    positions = [farm["farmer"], *farm["hands"]]
    tasks = [((4, y), "COLLECT_FERTILIZER", 55, None, None) for y in range(1, 5)]
    return positions, obs["private"]["inventories"], tasks, ACCESS


@pytest.mark.parametrize("seat", [0, 1])
def test_collection_pays_existing_land_gate_and_keeps_animals_fed(seat):
    env = world(seat)
    policy = get_last_callable(build(seed_capital=False))
    events = []
    for _ in range(22):
        observation = view(env, seat)
        money_before = observation["farms"][seat]["money"]
        action = policy(deepcopy(observation), env.configuration)
        if ["BUY_LAND"] in action["market"]:
            # The price plus original reserve is already actual cash.
            assert money_before > 1300
        actions = [action, {}] if seat == 0 else [{}, action]
        env.step(actions)
        events.append((observation["hour"], action))
    farm = env.state[0].observation.farms[seat]
    assert len(farm["unlocked_quadrants"]) == 2
    assert next(hour for hour, action in events if ["BUY_LAND"] in action["market"]) < 15
    assert any(
        order[:2] == ["SELL", "FERTILIZER"] for _, action in events for order in action["market"]
    )
    animals = [
        tile for row in farm["tiles"] for tile in row if isinstance(tile, dict) and "animal" in tile
    ]
    assert len(animals) == 4 and all(tile["fed_today"] for tile in animals)


def test_no_future_yield_or_oversubscribed_sources_finance_a_route():
    env = world()
    obs = view(env)
    positions, inventories, tasks, access = inputs(obs)
    assert investment_liquidity_possible(
        obs, env.configuration, positions, inventories, tasks, access, 260
    )
    for y in (1, 2, 3):
        obs["farms"][0]["tiles"][y][4]["fertilizer_available"] = False
    # One source cannot be counted once for every nearby worker or duplicate task.
    assert not investment_liquidity_possible(
        obs, env.configuration, positions, inventories, tasks * 4, access, 260
    )
    for y in (1, 2, 3, 4):
        obs["farms"][0]["tiles"][y][4]["fertilizer_available"] = False
    melon = game._new_plant("MELON", 0, 24)
    melon["yield_units"] = 4
    obs["farms"][0]["tiles"][0][0] = melon
    assert not investment_liquidity_possible(
        obs,
        env.configuration,
        positions,
        inventories,
        [((0, 0), "HARVEST", 70, None, None)],
        access,
        1,
    )


def test_input_reserves_and_storage_are_not_sale_collateral():
    env = world()
    obs = view(env)
    positions, inventories, tasks, access = inputs(obs)
    tasks.append(((0, 0), "FERTILIZE", 80, "FERTILIZER", None))
    assert not investment_liquidity_possible(
        obs, env.configuration, positions, inventories, tasks, access, 1
    )
    inventories[0]["WHEAT"] = 100
    assert not investment_liquidity_possible(
        obs, env.configuration, positions, inventories, [], access, 1
    )
    obs["private"]["shed"] = {"WHEAT": 100}
    assert not investment_liquidity_possible(
        obs, env.configuration, positions, inventories, tasks[:-1], access, 1
    )


def test_delivery_requires_real_round_trip_and_early_maintenance_slack():
    env = world()
    obs = view(env)
    _, _, tasks, access = inputs(obs)
    # At hour 11, one far worker cannot collect and return before hour 16.
    obs["hour"] = 11
    assert not investment_liquidity_possible(
        obs, env.configuration, [(0, 0)], [{}], tasks, access, 1
    )
    assert investment_liquidity_possible(
        obs, env.configuration, [(4, 4)], [{"MILK": 3}], [], access, 200
    )
    obs["hour"] = 12
    assert not investment_liquidity_possible(
        obs, env.configuration, [(4, 4)], [{"MILK": 3}], [], access, 1
    )


def test_no_blocked_investment_preserves_dispatch_and_duplicate_calls():
    env = world()
    obs = view(env)
    obs["farms"][0]["money"] = 10000
    current, challenger = (
        get_last_callable(fleet_build(cereal=True, budget_seconds=0.150)),
        get_last_callable(build()),
    )
    expected = current(deepcopy(obs), env.configuration)
    actual = challenger(deepcopy(obs), env.configuration)
    assert actual == expected
    assert challenger(deepcopy(obs), env.configuration) == actual
    # A reused process with a day/clock reset has no persistent capital target.
    obs.update(step=122, hour=2)
    challenger(deepcopy(obs), env.configuration)
    fresh = world()
    reset = view(fresh)
    assert challenger(deepcopy(reset), fresh.configuration) == get_last_callable(build())(
        deepcopy(reset), fresh.configuration
    )


def test_builder_preserves_frozen_budget_base_and_official_entrypoint():
    assert (
        hashlib.sha256(fleet_build(cereal=True, budget_seconds=0.150).encode()).hexdigest()
        == "fca083cdb5ac82dc4ad39a4227ef60ca57c948f819b565804aa706994f8e61ba"
    )
    assert build() == build()
    assert get_last_callable(build()).__name__ == "agent"
