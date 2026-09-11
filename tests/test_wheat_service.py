"""Observed wheat service contracts through the official interpreter."""

import gzip
from copy import deepcopy
from pathlib import Path

import pytest
from experiments.wheat_service import INCUMBENT, build
from kaggle_environments import make
from kaggle_environments.agent import get_last_callable
from kaggle_environments.envs.kaggriculture import kaggriculture as game
from kaggle_environments.utils import structify


def field(*, seat=0, day=10, hour=4, workers=1, money=500, seeds=0):
    env = make("kaggriculture", configuration={"seed": 17, "weedSpawnChance": 0})
    env.reset(2)
    obs = env.state[0].observation
    obs.update(step=day * 24 + hour, day=day, hour=hour)
    farm = obs.farms[seat]
    farm.money = money
    positions = [[4, 3], [3, 3], [2, 3]]
    farm.farmer, farm.hands = positions[0], positions[1:workers]
    private = env.state[seat].observation.private
    private.inventories = [{} for _ in range(workers)]
    private.seeds["WHEAT"] = seeds
    for x, y in positions[:workers]:
        tile = game._new_plant("WHEAT", max(0, day - 4), 24)
        tile.update(
            yield_units=1 + max(0, min(4, day) - 1),
            watered_today=True,
            consecutive_unwatered=0,
        )
        farm.tiles[y][x] = tile
    return env


def observed(env, seat=0):
    obs = deepcopy(env.state[seat].observation)
    for key in ("step", "day", "hour", "farms", "market", "town"):
        obs[key] = deepcopy(env.state[0].observation[key])
    return obs


def advance(env, action, seat=0):
    """Run the full game transition, including atomic seeds and market ordering."""
    step = env.state[0].observation["step"]
    for player in (0, 1):
        env.state[player].action = action if player == seat else {}
    game.interpreter(env.state, env)
    # The environment framework advances this bookkeeping field afterwards.
    env.state[0].observation.step = step + 1
    env.state = structify(env.state)


def namespace(base=None, **kwargs):
    result = {}
    exec(build(**kwargs), result)
    if base:
        result["_wheat_base_agent"] = base
    return result


def scripted_harvest(step, workers=1, market=()):
    def base(obs, cfg):
        action = ["HARVEST"] if obs["step"] == step else ["NORTH"]
        return {
            "farmer": action,
            "hands": [list(action) for _ in range(workers - 1)],
            "market": deepcopy(list(market)) if obs["step"] == step else [],
        }

    return base


@pytest.mark.parametrize("seat", [0, 1])
def test_harvest_buys_seed_then_observed_plant_and_water(seat):
    env = field(seat=seat)
    ns = namespace(scripted_harvest(244))
    obs = observed(env, seat)
    first = ns["agent"](obs, env.configuration)
    assert first["farmer"] == ["HARVEST"]
    assert first["market"] == [["BUY_SEED", "WHEAT", 1]]
    assert obs.private.seeds["WHEAT"] == 0
    advance(env, first, seat)
    assert env.state[0].observation.farms[seat].tiles[3][4] is None
    assert env.state[seat].observation.private.seeds["WHEAT"] == 1
    assert env.state[seat].observation.private.inventories[0]["WHEAT"] == 4
    second = ns["agent"](observed(env, seat), env.configuration)
    assert second["farmer"] == ["PLANT", "WHEAT"]
    advance(env, second, seat)
    assert env.state[0].observation.farms[seat].tiles[3][4]["planted_day"] == 10
    third = ns["agent"](observed(env, seat), env.configuration)
    assert third["farmer"] == ["WATER"]
    advance(env, third, seat)
    assert env.state[0].observation.farms[seat].tiles[3][4]["watered_today"]
    assert ns["agent"](observed(env, seat), env.configuration)["farmer"] == ["NORTH"]


def test_full_frozen_policy_executes_the_service_cycle():
    env = field(money=5000)
    ns = namespace()
    actions = []
    for _ in range(3):
        result = ns["agent"](observed(env), env.configuration)
        actions.append(result["farmer"])
        advance(env, result)
    assert actions == [["HARVEST"], ["PLANT", "WHEAT"], ["WATER"]]
    assert env.state[0].observation.farms[0].tiles[3][4]["watered_today"]


def test_two_contracts_reserve_seeds_before_other_original_planting():
    env = field(workers=3, seeds=3)
    env.state[0].observation.farms[0].tiles[3][2] = None
    seen = []

    def base(obs, cfg):
        if obs["step"] == 244:
            return {"farmer": ["HARVEST"], "hands": [["HARVEST"], ["PASS"]], "market": []}
        seen.append(obs["private"]["seeds"]["WHEAT"])
        return {"farmer": ["NORTH"], "hands": [["NORTH"], ["PLANT", "WHEAT"]], "market": []}

    ns = namespace(base)
    advance(env, ns["agent"](observed(env), env.configuration))
    before = observed(env)
    action = ns["agent"](before, env.configuration)
    assert seen == [1]
    assert before.private.seeds["WHEAT"] == 3
    assert [action["farmer"], *action["hands"]] == [["PLANT", "WHEAT"]] * 3
    advance(env, action)
    assert env.state[0].observation.private.seeds["WHEAT"] == 0
    assert all(env.state[0].observation.farms[0].tiles[3][x]["crop"] == "WHEAT" for x in (2, 3, 4))


def test_defensive_reservation_prevents_atomic_failure_when_base_overrequests():
    env = field(workers=2, seeds=1)
    env.state[0].observation.farms[0].tiles[3][3] = None

    def base(obs, cfg):
        return {
            "farmer": ["HARVEST"] if obs["step"] == 244 else ["NORTH"],
            "hands": [["PASS"] if obs["step"] == 244 else ["PLANT", "WHEAT"]],
            "market": [],
        }

    ns = namespace(base)
    advance(env, ns["agent"](observed(env), env.configuration))
    action = ns["agent"](observed(env), env.configuration)
    assert action["farmer"] == ["PLANT", "WHEAT"]
    assert action["hands"] == [["PASS"]]
    advance(env, action)
    assert env.state[0].observation.farms[0].tiles[3][4]["crop"] == "WHEAT"


@pytest.mark.parametrize("failure", ["harvest", "plant", "occupied", "moved", "missing_worker"])
def test_failed_or_invalidated_actions_release_commitments(failure):
    env = field(workers=2)
    ns = namespace(scripted_harvest(244, workers=2))
    first = ns["agent"](observed(env), env.configuration)
    if failure == "harvest":
        first["farmer"] = ["PASS"]
    advance(env, first)
    if failure == "occupied":
        env.state[0].observation.farms[0].tiles[3][4] = game._new_plant("CARROT", 10, 24)
    elif failure == "moved":
        env.state[0].observation.farms[0].farmer = [4, 2]
    elif failure == "missing_worker":
        env.state[0].observation.farms[0].hands = []
        env.state[0].observation.private.inventories = env.state[0].observation.private.inventories[
            :1
        ]
    second = ns["agent"](observed(env), env.configuration)
    if failure == "plant":
        second["farmer"] = ["PASS"]
        advance(env, second)
        assert ns["agent"](observed(env), env.configuration)["farmer"] == ["NORTH"]
    elif failure == "missing_worker":
        assert 1 not in ns["_WHEAT_SERVICE_MEMORY"][0]["plans"]
    else:
        assert second["farmer"] == ["NORTH"]


@pytest.mark.parametrize("day,hour,price", [(9, 4, 25), (27, 4, 25), (10, 22, 25), (10, 4, 10)])
def test_opening_terminal_late_hour_and_unprofitable_rotations_do_not_start(day, hour, price):
    env = field(day=day, hour=hour)
    env.state[0].observation.market.prices["WHEAT"] = price
    ns = namespace(scripted_harvest(day * 24 + hour))
    action = ns["agent"](observed(env), env.configuration)
    assert action["market"] == []
    assert ns["_WHEAT_SERVICE_MEMORY"][0]["plans"] == {}


def test_seed_orders_respect_cash_existing_orders_and_market_limit():
    env = field(money=19)
    ns = namespace(scripted_harvest(244, market=[["BUY_SEED", "WHEAT", 1]]))
    action = ns["agent"](observed(env), env.configuration)
    assert action["market"] == [["BUY_SEED", "WHEAT", 1]]
    advance(env, action)
    assert env.state[0].observation.farms[0].money == 9
    assert ns["agent"](observed(env), env.configuration)["farmer"] == ["PLANT", "WHEAT"]

    for money, orders in [(9, []), (500, [["SELL", "WHEAT", 1]] * 10)]:
        env = field(money=money)
        ns = namespace(scripted_harvest(244, market=orders))
        action = ns["agent"](observed(env), env.configuration)
        assert action["market"] == orders
        assert not ns["_WHEAT_SERVICE_MEMORY"][0]["plans"]


def test_partial_funding_and_failed_purchase_cannot_create_seed_contention():
    env = field(workers=2, money=15)
    ns = namespace(scripted_harvest(244, workers=2))
    first = ns["agent"](observed(env), env.configuration)
    assert first["market"] == [["BUY_SEED", "WHEAT", 1]]
    advance(env, first)
    second = ns["agent"](observed(env), env.configuration)
    assert [second["farmer"], *second["hands"]].count(["PLANT", "WHEAT"]) == 1
    advance(env, second)
    assert env.state[0].observation.farms[0].tiles[3][4]["crop"] == "WHEAT"
    assert env.state[0].observation.farms[0].tiles[3][3] is None

    env = field()
    ns = namespace(scripted_harvest(244))
    first = ns["agent"](observed(env), env.configuration)
    first["market"] = []
    advance(env, first)
    assert ns["agent"](observed(env), env.configuration)["farmer"] == ["NORTH"]
    assert not ns["_WHEAT_SERVICE_MEMORY"][0]["plans"]


def test_incumbent_hiring_and_animal_purchase_keep_their_cash_reservations():
    env = field(money=11)
    ns = namespace(scripted_harvest(244, market=[["HIRE"]]))
    action = ns["agent"](observed(env), env.configuration)
    assert action["market"] == [["HIRE"], ["BUY_SEED", "WHEAT", 1]]
    advance(env, action)
    assert env.state[0].observation.farms[0].money == 0
    assert len(env.state[0].observation.farms[0].hands) == 1
    assert env.state[0].observation.private.seeds["WHEAT"] == 1

    env = field(money=405)
    ns = namespace(scripted_harvest(244, market=[["BUY_ANIMAL", "COW", 1]]))
    action = ns["agent"](observed(env), env.configuration)
    assert action["market"] == [["BUY_ANIMAL", "COW", 1]]
    advance(env, action)
    assert env.state[0].observation.farms[0].money == 5
    assert not ns["_WHEAT_SERVICE_MEMORY"][0]["plans"]


def test_opening_actions_match_frozen_policy_before_activation():
    ns = namespace()
    for seat in (0, 1):
        for day in (0, 3, 6, 9):
            env = field(day=day, seat=seat, money=3000, workers=3)
            obs = observed(env, seat)
            assert ns["agent"](obs, env.configuration) == ns["_wheat_base_agent"](
                deepcopy(obs), env.configuration
            )


def test_duplicate_calls_cache_safely_and_new_episode_resets():
    env = field()
    ns = namespace(scripted_harvest(244))
    obs = observed(env)
    first = ns["agent"](obs, env.configuration)
    memory = deepcopy(ns["_WHEAT_SERVICE_MEMORY"])
    first["market"].clear()
    repeated = ns["agent"](obs, env.configuration)
    assert repeated["market"] == [["BUY_SEED", "WHEAT", 1]]
    assert ns["_WHEAT_SERVICE_MEMORY"] == memory
    obs.update(step=0, day=0, hour=0)
    assert ns["agent"](obs, env.configuration)["farmer"] == ["NORTH"]
    assert not ns["_WHEAT_SERVICE_MEMORY"][0]["plans"]


def test_day_reset_and_skipped_observation_discard_contracts():
    for day, step in [(11, 264), (10, 247)]:
        env = field()
        ns = namespace(scripted_harvest(244))
        advance(env, ns["agent"](observed(env), env.configuration))
        obs = observed(env)
        obs.update(day=day, hour=step % 24, step=step)
        assert ns["agent"](obs, env.configuration)["farmer"] == ["NORTH"]
        assert not ns["_WHEAT_SERVICE_MEMORY"][0]["plans"]


def test_last_feasible_same_day_cycle_waters_before_the_daily_reset():
    env = field(hour=21)
    ns = namespace(scripted_harvest(261))
    operations = []
    for _ in range(3):
        action = ns["agent"](observed(env), env.configuration)
        operations.append(action["farmer"])
        advance(env, action)
    assert operations == [["HARVEST"], ["PLANT", "WHEAT"], ["WATER"]]
    assert env.state[0].observation.day == 11
    tile = env.state[0].observation.farms[0].tiles[3][4]
    assert tile["crop"] == "WHEAT" and tile["consecutive_unwatered"] == 0
    assert not ns["_WHEAT_SERVICE_MEMORY"][0]["plans"]


def test_both_seats_can_keep_independent_contracts_in_one_process():
    environments = [field(seat=seat) for seat in (0, 1)]
    ns = namespace(scripted_harvest(244))
    for seat, env in enumerate(environments):
        advance(env, ns["agent"](observed(env, seat), env.configuration), seat)
    for seat, env in enumerate(environments):
        assert ns["agent"](observed(env, seat), env.configuration)["farmer"] == ["PLANT", "WHEAT"]


def test_urgent_feed_departure_prevents_new_local_commitment():
    env = field(hour=18)
    animal = game._new_animal("SHEEP", 0)
    animal["consecutive_unfed"] = 1
    env.state[0].observation.farms[0].tiles[3][0] = animal
    ns = namespace(scripted_harvest(258))
    assert ns["agent"](observed(env), env.configuration)["market"] == []
    assert not ns["_WHEAT_SERVICE_MEMORY"][0]["plans"]


def test_final_allowed_cohort_can_mature_and_sell_before_the_terminal_window():
    env = field(day=26)
    ns = namespace(scripted_harvest(628))
    for _ in range(3):
        advance(env, ns["agent"](observed(env), env.configuration))
    farm, private = env.state[0].observation.farms[0], env.state[0].observation.private
    game._daily_refresh_plants(farm, 26, 24)
    game._daily_refresh_plants(farm, 27, 24)
    old_inventory = private.inventories[0]["WHEAT"]
    for action in (["WATER"], ["HARVEST"], ["SOUTH"], ["DROP"]):
        game._apply_unit_action(farm, private, 0, action, 10, 28, 24, 100)
    assert private.shed["WHEAT"] == old_inventory + 2
    env.state[0].observation.update(day=28, hour=5, step=677)
    before_cash = farm.money
    advance(env, {"market": [["SELL", "WHEAT", 2]]})
    assert env.state[0].observation.farms[0].money - before_cash > game.CROPS["WHEAT"]["seed"]


def test_fresh_process_needs_no_contract_state_and_official_loader_selects_wrapper():
    source = build()
    assert get_last_callable(source).__name__ == "agent"
    env = field()
    ns = namespace(scripted_harvest(244))
    advance(env, ns["agent"](observed(env), env.configuration))
    fresh = namespace(scripted_harvest(244))
    assert fresh["agent"](observed(env), env.configuration)["farmer"] == ["NORTH"]
    assert not fresh["_WHEAT_SERVICE_MEMORY"][0]["plans"]
    raw = gzip.decompress((Path("reports/sources") / f"{INCUMBENT}.py.gz").read_bytes())
    assert build(enabled=False).encode() == raw
