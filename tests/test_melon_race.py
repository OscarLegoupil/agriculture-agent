"""Official action contracts for the complete early-melon pipeline."""

from copy import deepcopy

import pytest
from experiments.melon_race import build
from kaggle_environments import make
from kaggle_environments.envs.kaggriculture import kaggriculture as game


@pytest.fixture(scope="module")
def policy():
    namespace = {}
    exec(build(), namespace)
    return namespace["agent"]


def grown_melon(through_day, fertilizer_day=None, fertilizer_after_water=False):
    farm = game._new_farm(10, 3000)
    private = game._new_private()
    farm["farmer"] = [4, 4]
    farm["tiles"][4][4] = game._new_plant("MELON", 0, 24)
    private["inventories"][0] = {"FERTILIZER": 1}
    for day in range(through_day + 1):
        operations = [["WATER"]]
        if day == fertilizer_day:
            operations.insert(1 if fertilizer_after_water else 0, ["FERTILIZE"])
        for operation in operations:
            game._apply_unit_action(farm, private, 0, operation, 10, day, 24)
        game._daily_refresh_plants(farm, day, 24)
    return farm, private


@pytest.mark.parametrize(
    "fertilizer_day,after_water", [(7, False), (7, True), (8, False), (8, True)]
)
def test_early_fertilizer_reaches_cap_before_first_legal_harvest(fertilizer_day, after_water):
    ordinary, ordinary_private = grown_melon(9)
    prepared, prepared_private = grown_melon(9, fertilizer_day, after_water)
    assert ordinary["tiles"][4][4]["yield_units"] == 5
    assert prepared["tiles"][4][4]["yield_units"] == 6
    # A full tile still cannot harvest before age 10.
    game._apply_unit_action(prepared, prepared_private, 0, ["HARVEST"], 10, 9, 24)
    assert prepared_private["inventories"][0].get("MELON", 0) == 0
    game._apply_unit_action(prepared, prepared_private, 0, ["HARVEST"], 10, 10, 24)
    assert prepared_private["inventories"][0]["MELON"] == 6
    game._apply_unit_action(ordinary, ordinary_private, 0, ["HARVEST"], 10, 10, 24)
    assert ordinary_private["inventories"][0]["MELON"] == 5


def at_day(day):
    env = make("kaggriculture", configuration={"seed": 17})
    env.reset(2)
    for _ in range(day * 24):
        env.step([{}, {}])
    return env


def agent_observation(env, seat):
    # The file-agent runner merges shared fields into seat 1's callback.
    obs = deepcopy(env.state[seat].observation)
    for name in ("step", "day", "hour", "farms", "market", "town"):
        obs[name] = deepcopy(env.state[0].observation[name])
    return obs


def test_candidate_buys_picks_up_and_applies_preparation_before_maturity(policy):
    env = at_day(7)
    obs = env.state[0].observation
    farm = obs.farms[0]
    farm.money = 350
    for row in farm.tiles:
        for x, tile in enumerate(row):
            if tile != "LOCKED":
                row[x] = {"kind": "WEED"}
    grown, _ = grown_melon(6)
    farm.tiles[3][4] = deepcopy(grown["tiles"][4][4])
    obs.private.shed.clear()
    obs.private.inventories = [{}]
    first = policy(obs, env.configuration)
    assert ["BUY_PRODUCT", "FERTILIZER", 1] in first["market"]
    assert first["farmer"] != ["FERTILIZE"]
    env.step([first, {}])
    assert env.state[0].observation.private.shed["FERTILIZER"] == 1
    operations = []
    for _ in range(9):
        current = env.state[0].observation
        action = policy(current, env.configuration)
        operations.extend([action["farmer"], *action["hands"]])
        env.step([action, {}])
        if env.state[0].observation.farms[0].tiles[3][4]["fertilized_until_day"] >= 9:
            break
    assert ["PICKUP", "FERTILIZER", 1] in operations
    assert ["FERTILIZE"] in operations
    assert env.state[0].observation.farms[0].tiles[3][4]["fertilized_until_day"] == 9


@pytest.mark.parametrize("seat", [0, 1])
def test_prepared_melon_harvests_then_drops_and_sells_in_one_following_turn(policy, seat):
    env = at_day(10)
    obs = env.state[seat].observation
    farm = env.state[0].observation.farms[seat]
    farm.money = 0
    grown, _ = grown_melon(9, 7)
    farm.farmer = [4, 4]
    farm.tiles[4][4] = deepcopy(grown["tiles"][4][4])
    obs.private.shed.clear()
    obs.private.inventories = [{}]
    actions = [{}, {}]
    actions[seat] = policy(agent_observation(env, seat), env.configuration)
    assert actions[seat]["farmer"] == ["HARVEST"]
    env.step(actions)
    obs = env.state[seat].observation
    actions[seat] = policy(agent_observation(env, seat), env.configuration)
    assert actions[seat]["farmer"] == ["DROP"]
    assert ["SELL", "MELON", 6] in actions[seat]["market"]
    env.step(actions)
    result = env.state[seat].observation
    assert result.private.shed.get("MELON", 0) == 0
    assert result.farms[seat].money > 1400


def test_delivery_worker_does_not_reserve_the_remaining_ripe_melon(policy):
    env = at_day(10)
    obs = env.state[0].observation
    farm = obs.farms[0]
    farm.money = 0
    farm.farmer = [4, 4]
    farm.hands = [[4, 3]]
    farm.hires_today = 1
    grown, _ = grown_melon(9, 7)
    farm.tiles[4][3] = deepcopy(grown["tiles"][4][4])
    obs.private.shed.clear()
    obs.private.inventories = [{"MELON": 6}, {}]
    action = policy(obs, env.configuration)
    assert action["farmer"] == ["DROP"]
    assert action["hands"][0] in (["SOUTH"], ["WEST"])


def test_last_departure_feeding_still_preempts_the_melon_race(policy):
    env = at_day(10)
    obs = env.state[0].observation
    farm = obs.farms[0]
    farm.money = 0
    farm.farmer = [4, 4]
    grown, _ = grown_melon(9, 7)
    farm.tiles[4][4] = deepcopy(grown["tiles"][4][4])
    animal = game._new_animal("SHEEP", 0)
    animal["consecutive_unfed"] = 1
    farm.tiles[2][4] = animal
    obs.private.shed.clear()
    obs.private.inventories = [{"WHEAT": 1}]
    callback = agent_observation(env, 0)
    callback.update(step=261, hour=21)
    assert policy(callback, env.configuration)["farmer"] == ["NORTH"]


def test_ablation_without_changes_recovers_incumbent():
    import gzip
    from pathlib import Path

    from experiments.melon_race import INCUMBENT

    raw = gzip.decompress((Path("reports/sources") / f"{INCUMBENT}.py.gz").read_bytes())
    assert build(fertilizer=False, race=False, same_turn_sales=False) == raw.decode()
