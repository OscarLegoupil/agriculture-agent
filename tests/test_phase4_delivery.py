"""Official transitions supporting a one-turn delivery/sale improvement."""

import copy

import pytest
from kaggle_environments import make
from scripts.phase4_delivery import build


@pytest.fixture(scope="module")
def finalize():
    namespace = {}
    exec(build(), namespace)
    return namespace["immediate_delivery_sales"]


def setup():
    env = make("kaggriculture", configuration={"seed": 17})
    env.reset(2)
    env.step([{}, {}])  # Step 1 has no scheduled town consumption.
    obs = env.state[0].observation
    obs.farms[0].farmer = [4, 4]
    obs.private.inventories[0] = {"MILK": 3, "WHEAT": 2}
    return env, obs


def test_drop_is_sold_in_same_official_turn_without_selling_feed(finalize):
    env, obs = setup()
    before = copy.deepcopy(obs)
    cash = obs.farms[0].money
    orders = finalize(obs, env.configuration, [["DROP"]], [])
    assert orders == [["SELL", "MILK", 3]]
    assert obs == before
    env.step([{"farmer": ["DROP"], "market": orders}, {}])
    assert env.state[0].observation.private.shed["MILK"] == 0
    assert env.state[0].observation.private.shed["WHEAT"] == 2
    assert env.state[0].observation.farms[0].money > cash


def test_capacity_respects_inventory_order_and_pickups_before_drops(finalize):
    env, obs = setup()
    obs.private.shed["WHEAT"] = 98
    orders = finalize(obs, env.configuration, [["DROP"]], [])
    assert orders == [["SELL", "MILK", 2]]
    env.step([{"farmer": ["DROP"], "market": orders}, {}])
    assert env.state[0].observation.private.shed["WHEAT"] == 98
    assert env.state[0].observation.private.shed["MILK"] == 0
    assert not env.state[0].observation.private.inventories[0]


def test_sequential_pickup_frees_space_but_later_pickup_does_not(finalize):
    env, obs = setup()
    obs.farms[0].hands = [[4, 4]]
    obs.private.shed["WHEAT"] = 100
    obs.private.inventories = [{}, {"MILK": 3}]
    actions = [["PICKUP", "WHEAT", 3], ["DROP"]]
    orders = finalize(obs, env.configuration, actions, [])
    assert orders == [["SELL", "MILK", 3]]
    env.step([{"farmer": actions[0], "hands": actions[1:], "market": orders}, {}])
    assert env.state[0].observation.private.shed["MILK"] == 0
    assert env.state[0].observation.private.inventories[0]["WHEAT"] == 3
    env, obs = setup()
    obs.farms[0].hands = [[4, 4]]
    obs.private.shed["WHEAT"] = 100
    obs.private.inventories = [{"MILK": 3}, {}]
    assert not finalize(obs, env.configuration, [["DROP"], ["PICKUP", "WHEAT", 3]], [])


def test_town_consumes_after_market_so_consumption_turn_is_not_advanced(finalize):
    env, obs = setup()
    while env.state[0].observation.step < 4:
        env.step([{}, {}])
    obs = env.state[0].observation
    obs.town.unlocked_shops = ["PIZZA_SHOP"]
    inventory = obs.market.inventory["MILK"]
    obs.private.inventories[0] = {"MILK": 3}
    assert not finalize(obs, env.configuration, [["DROP"]], [])
    env.step([{"farmer": ["DROP"]}, {}])
    assert env.state[0].observation.private.shed["MILK"] == 3
    assert env.state[0].observation.market.inventory["MILK"] == inventory - 1


def test_existing_buy_order_positions_and_market_limit_are_preserved(finalize):
    env, obs = setup()
    orders = [["BUY_PRODUCT", "WHEAT", 1]] * 10
    assert finalize(obs, env.configuration, [["DROP"]], orders) == orders
    orders = [["BUY_PRODUCT", "WHEAT", 1], ["SELL", "MILK", 1], *orders[:8]]
    obs.private.shed["MILK"] = 1
    result = finalize(obs, env.configuration, [["DROP"]], orders)
    assert result[1] == ["SELL", "MILK", 4]
    assert result[:1] == orders[:1] and result[2:] == orders[2:]


def test_travel_toward_shed_is_not_a_same_turn_delivery(finalize):
    env, obs = setup()
    obs.farms[0].farmer = [3, 4]
    assert not finalize(obs, env.configuration, [["EAST"]], [])
    assert not finalize(obs, env.configuration, [["DROP"]], [])


def test_nonproduct_shed_placement_still_reserves_storage(finalize):
    env, obs = setup()
    obs.farms[0].hands = [[4, 4]]
    obs.private.shed["WHEAT"] = 99
    obs.private.inventories = [{"COW": 1}, {"MILK": 3}]
    actions = [["PLACE", "COW"], ["DROP"]]
    assert not finalize(obs, env.configuration, actions, [])
    env.step([{"farmer": actions[0], "hands": actions[1:]}, {}])
    assert env.state[0].observation.private.shed["COW"] == 1
    assert env.state[0].observation.private.shed["MILK"] == 0
