"""Official observations verify the retained bridge and changed production orders."""

from copy import deepcopy

import pytest
from experiments.daily_routes import build as fleet_build
from experiments.diversified_calendar import build
from kaggle_environments import make
from kaggle_environments.agent import get_last_callable
from kaggle_environments.envs.kaggriculture import kaggriculture as game


def world(wheat=7):
    env = make("kaggriculture", configuration={"seed": 5000})
    env.reset()
    obs = deepcopy(env.state[0].observation)
    farm = obs["farms"][0]
    game._do_buy_land(farm, 10)
    farm["money"] = 10000
    obs.update(day=10, hour=12, step=252)
    slots = [(x, y) for y in range(5) for x in range(10)]
    for index, (x, y) in enumerate(slots[: 20 + wheat]):
        farm["tiles"][y][x] = (
            game._new_animal("COW" if index < 2 else "SHEEP", 0)
            if index < 4
            else game._new_plant("STRAWBERRY" if index < 20 else "WHEAT", 8, 24)
        )
    return obs, dict(env.configuration)


@pytest.mark.parametrize("compact", [False, True])
def test_new_calendar_keeps_seven_wheat_before_tomatoes(compact):
    full, cfg = world()
    scarce, _ = world(wheat=3)
    policy = get_last_callable(build(compact_herd=compact))
    assert any(order[:2] == ["BUY_SEED", "TOMATO"] for order in policy(full, cfg)["market"])
    # At the first available admission the capital bridge still takes priority.
    action = get_last_callable(build(compact_herd=compact))(scarce, cfg)
    assert next(order[1] for order in action["market"] if order[0] == "BUY_SEED") == "WHEAT"


def test_compact_herd_prevents_additional_animal_purchase():
    obs, cfg = world()
    old = get_last_callable(build())(deepcopy(obs), cfg)
    new = get_last_callable(build(compact_herd=True))(deepcopy(obs), cfg)
    assert any(order[0] == "BUY_ANIMAL" for order in old["market"])
    assert all(order[0] != "BUY_ANIMAL" for order in new["market"])


@pytest.mark.parametrize("seat", [0, 1])
def test_untouched_initial_action_and_official_entrypoint(seat):
    env = make("kaggriculture", configuration={"seed": 5000})
    env.reset()
    obs = deepcopy(env._Environment__get_shared_state(seat).observation)
    old = get_last_callable(fleet_build(cereal=True, budget_seconds=0.150))(
        deepcopy(obs), env.configuration
    )
    for compact in (False, True):
        policy = get_last_callable(build(compact_herd=compact))
        assert policy.__name__ == "agent"
        assert policy(deepcopy(obs), env.configuration) == old
