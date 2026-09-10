"""Executable town-demand and market-floor contracts use official helpers."""

from types import SimpleNamespace

import pytest
from scripts.phase4_forecast_contract import expected_town_demand, sold_inventory


@pytest.mark.parametrize(
    "step,shops",
    [(48, []), (72, ["YARN_STORE"]), (95, ["YARN_STORE"]), (80, ["YARN_STORE", "YARN_STORE"])],
)
def test_current_interval_expected_demand_matches_actual_consume(step, shops):
    from kaggle_environments.envs.kaggriculture import kaggriculture as game

    market = game._new_market()
    obs = dict(step=step, day=step // 24, town={"unlocked_shops": shops})
    target = expected_town_demand(obs, obs["day"] + 1, game.SHOPS, market["inventory"])
    state = [SimpleNamespace(observation=SimpleNamespace(market=market, town=obs["town"]))]
    env = SimpleNamespace(configuration={})
    for turn in range(step, (obs["day"] + 1) * 24):
        game._town_consume(env, state, turn)
    assert target == {item: 10000 - count for item, count in market["inventory"].items()}


def test_unlock_consumption_begins_after_unlock_boundary():
    from kaggle_environments.envs.kaggriculture import kaggriculture as game

    obs = dict(step=48, day=2, town={"unlocked_shops": []})
    items = game._new_market()["inventory"]
    assert expected_town_demand(obs, 3, game.SHOPS, items)["WOOL"] == 1
    assert expected_town_demand(obs, 4, game.SHOPS, items)["WOOL"] == 2.5


def test_official_unlock_draws_full_catalog_with_replacement_and_caps_instances(monkeypatch):
    from kaggle_environments.envs.kaggriculture import kaggriculture as game

    catalogs = []

    class FixedDraw:
        def __init__(self, seed):
            pass

        def choice(self, options):
            catalogs.append(list(options))
            return options[0]

    monkeypatch.setattr(game.random, "Random", FixedDraw)
    town = {"unlocked_shops": []}
    state = [SimpleNamespace(observation=SimpleNamespace(farms=[], town=town))]
    env = SimpleNamespace(configuration={}, info={"seed": 0})
    game._end_of_day(state, env, 1)
    assert town["unlocked_shops"] == []
    for day in range(2, 29, 3):
        game._end_of_day(state, env, day)
    assert catalogs == [sorted(game.SHOPS)] * 8
    assert town["unlocked_shops"] == [sorted(game.SHOPS)[0]] * 8


@pytest.mark.parametrize("item", ["WOOL", "MILK", "STRAWBERRY", "FERTILIZER"])
def test_dollar_floor_supply_matches_sequential_official_sales(item):
    from kaggle_environments.envs.kaggriculture import kaggriculture as game

    market = game._new_market()
    farm, private = {"money": 0}, {"shed": {item: 1000}}
    for _ in range(1000):
        price = game.market_price(item, market["inventory"][item])
        assert game._commit_unit("SELL", item, price, farm, private, market)
    modeled = sold_inventory(
        10000, 1000, None, lambda inventory, _: game.market_price(item, inventory)
    )
    assert modeled == market["inventory"][item]
    assert modeled < 11000
