"""Observed rival output can trigger an executable harvest-and-sale route."""

from copy import deepcopy

import pytest
from experiments.daily_routes import build as fleet_build
from experiments.market_collection import build, urgent_products
from kaggle_environments import make
from kaggle_environments.agent import get_last_callable
from kaggle_environments.envs.kaggriculture import kaggriculture as game


def world(seat=0):
    env = make("kaggriculture", configuration={"seed": 5000})
    env.reset()
    obs = deepcopy(env.state[0].observation)
    obs.update(player=seat, day=18, hour=0, step=432)
    farm = game._new_farm(10, 20000)
    farm["farmer"] = [4, 4]
    tile = game._new_animal("SHEEP", 9)
    tile.update(yield_units=6, fed_today=True, cared_today=False, fertilizer_available=True)
    farm["tiles"][3][4] = tile
    obs["farms"][seat] = farm
    obs["private"] = {"shed": {}, "seeds": {}, "inventories": [{}]}
    for x in range(4):
        rival = game._new_animal("SHEEP", 8)
        rival["yield_units"] = 6
        obs["farms"][1 - seat]["tiles"][0][x] = rival
    obs["market"]["inventory"]["WOOL"] = 10040
    game._refresh_prices(obs["market"])
    return obs, dict(env.configuration)


def test_only_visible_rival_pressure_triggers_race():
    obs, _ = world()
    assert "WOOL" in urgent_products(obs)
    for row in obs["farms"][1]["tiles"]:
        for tile in row:
            if isinstance(tile, dict):
                tile["yield_units"] = 0
    assert urgent_products(obs) == {"MELON"}
    # Owned/private stock cannot fabricate unavailable rival inventory.
    obs["private"]["shed"]["WOOL"] = 100
    assert urgent_products(obs) == {"MELON"}


def test_floor_quote_has_no_avoidable_price_loss():
    obs, _ = world()
    obs["market"]["inventory"]["WOOL"] = 11000
    game._refresh_prices(obs["market"])
    assert urgent_products(obs) == {"MELON"}


@pytest.mark.parametrize("seat", [0, 1])
def test_rushed_wool_reaches_shed_and_same_turn_sale_before_care(seat):
    obs, cfg = world(seat)
    policy = get_last_callable(build())
    actions = []
    farm = obs["farms"][seat]
    private = obs["private"]
    for hour in range(6):
        obs.update(hour=hour, step=432 + hour)
        action = policy(deepcopy(obs), cfg)
        actions.append(action["farmer"])
        game._apply_unit_action(farm, private, 0, action["farmer"], 10, 18, 24, 100)
        if action["farmer"] == ["DROP"]:
            assert private["shed"].get("WOOL") == 6
            assert ["SELL", "WOOL", 6] in action["market"]
            before = farm["money"]
            for _ in range(6):
                quote = game.market_price(
                    "WOOL", obs["market"]["inventory"]["WOOL"], obs["market"].get("params")
                )
                game._commit_unit("SELL", "WOOL", quote, farm, private, obs["market"])
            assert farm["money"] > before
            break
    else:
        pytest.fail("Rushed harvest never reached its sale opportunity")
    assert ["HARVEST"] in actions and ["CARE"] not in actions
    assert farm["tiles"][3][4]["fed_today"]


def test_no_rival_supply_preserves_a_cold_opening_decision():
    env = make("kaggriculture", configuration={"seed": 5000})
    env.reset()
    for seat in (0, 1):
        obs = deepcopy(env._Environment__get_shared_state(seat).observation)
        old = get_last_callable(fleet_build(cereal=True, budget_seconds=0.150))
        new = get_last_callable(build())
        assert new(deepcopy(obs), env.configuration) == old(deepcopy(obs), env.configuration)
