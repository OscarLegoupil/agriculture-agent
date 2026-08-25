"""Tests for the typed env wrappers.

Runs a short episode with two built-in agents and, at each turn, parses the
raw observation into `Observation` and asserts basic invariants. This gives
us de facto coverage of every code path in observation.py because a real
episode produces every tile kind and structure.
"""

from __future__ import annotations

from kaggle_environments import make

from kaggriculture.env import Empty, Farm, Locked, Observation, actions, constants


def test_constants_reflect_kaggriculture_source() -> None:
    assert set(constants.CROPS) == {"WHEAT", "CARROT", "TOMATO", "STRAWBERRY", "MELON"}
    assert set(constants.ANIMALS) == {"GOOSE", "COW", "SHEEP"}
    assert constants.MARKET_I0 == 10_000
    assert constants.PRICE_FLOOR == 1
    assert constants.LAND_PRICES == (1_000, 2_000, 4_000)
    assert constants.LAND_ORDER == ("NE", "SW", "SE")
    assert set(constants.MARKET_PARAMS) == set(constants.PRODUCTS)


def test_action_builders_return_expected_lists() -> None:
    assert actions.pass_() == ["PASS"]
    assert actions.move("NORTH") == ["NORTH"]
    assert actions.plant("WHEAT") == ["PLANT", "WHEAT"]
    assert actions.pickup("EGG", 3) == ["PICKUP", "EGG", 3]
    assert actions.sell("MELON", 5) == ["SELL", "MELON", 5]
    assert actions.buy_land() == ["BUY_LAND"]

    a = actions.action(
        farmer=actions.plant("CARROT"),
        market=[actions.buy_seed("CARROT", 2), actions.hire()],
    )
    assert a == {
        "farmer": ["PLANT", "CARROT"],
        "hands": [],
        "market": [["BUY_SEED", "CARROT", 2], ["HIRE"]],
    }


def test_observation_from_dict_over_a_real_episode() -> None:
    env = make("kaggriculture", configuration={"episodeSteps": 240, "seed": 42})
    env.run(["pass", "starter"])

    starting_money = float(env.configuration.startingMoney)

    for step in env.steps:
        for player_id, agent_state in enumerate(step):
            raw = dict(agent_state.observation)
            raw.setdefault("player", player_id)
            if "farms" not in raw:
                continue
            obs = Observation.from_dict(raw)

            assert obs.player == player_id
            assert 0 <= obs.hour < 24
            assert len(obs.farms) == 2
            for farm in obs.farms:
                assert isinstance(farm, Farm)
                assert farm.money >= 0
                assert len(farm.tiles) == 10
                assert all(len(row) == 10 for row in farm.tiles)
                assert "NW" in farm.unlocked_quadrants

            assert obs.me.money >= 0
            assert obs.opponent is obs.farms[1 - player_id]
            for product in constants.PRODUCTS:
                assert product in obs.market.inventory
                assert product in obs.market.prices
                assert obs.market.prices[product] >= constants.PRICE_FLOOR

    # Sanity: at step 0 both players start with startingMoney.
    first = Observation.from_dict({**dict(env.steps[0][0].observation), "player": 0})
    assert first.farms[0].money == starting_money
    assert first.farms[1].money == starting_money


def test_locked_tiles_present_at_episode_start() -> None:
    env = make("kaggriculture", configuration={"episodeSteps": 1, "seed": 0})
    env.run(["pass", "pass"])
    obs = Observation.from_dict({**dict(env.steps[0][0].observation), "player": 0})
    flat = [t for row in obs.me.tiles for t in row]
    assert any(isinstance(t, Locked) for t in flat)
    assert any(isinstance(t, Empty) for t in flat)
    # Only NW starts unlocked (25 tiles).
    assert sum(isinstance(t, Empty) for t in flat) == 25
    assert sum(isinstance(t, Locked) for t in flat) == 75
