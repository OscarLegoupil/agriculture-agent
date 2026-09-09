"""Policy regressions for input logistics and finite-season decisions."""

from kaggle_environments import make

from kaggriculture.agent.competitive import agent, crop_value


def test_new_melons_cannot_repay_in_one_day():
    assert crop_value("MELON", 28, 250, 1, True) == float("-inf")


def test_seedless_opening_is_valid_and_deterministic():
    env = make("kaggriculture", configuration={"seed": 0})
    obs = env.reset(2)[0].observation
    assert agent(obs) == agent(obs)
    assert agent(obs)["farmer"][0] != "PLANT"


def test_worker_keeps_feed_for_hungry_cow():
    from kaggle_environments.envs.kaggriculture import kaggriculture as game

    env = make("kaggriculture", configuration={"seed": 0})
    obs = env.reset(2)[0].observation
    obs.farms[0].tiles[4][4] = game._new_animal("COW", 0)
    obs.private.inventories[0]["WHEAT"] = 3
    assert agent(obs)["farmer"] == ["FEED"]


def test_malformed_observation_has_cheap_fallback():
    assert agent({}) == {"farmer": ["PASS"], "hands": [], "market": []}
