"""The commercial-wheat alternative preserves startup and funds real seeds."""

from copy import deepcopy

from experiments.crop_rotation import build
from kaggle_environments import make
from kaggle_environments.agent import get_last_callable
from kaggle_environments.envs.kaggriculture import kaggriculture as game

from kaggriculture.agent.competitive import agent


def test_rotation_preserves_opening_before_the_financing_cohort_is_complete():
    candidate = get_last_callable(build())
    env = make("kaggriculture", configuration={"seed": 5000})
    env.reset(2)
    for _ in range(192):
        obs = deepcopy(env.state[0].observation)
        expected = agent(deepcopy(obs), dict(env.configuration))
        assert candidate(deepcopy(obs), dict(env.configuration)) == expected
        env.step([expected, {}])


def test_financed_berry_capacity_admits_commercial_wheat_with_real_purchase_delay():
    env = make("kaggriculture", configuration={"seed": 5000})
    env.reset(2)
    obs = env.state[0].observation
    obs.update(day=11, hour=8, step=272)
    farm = obs.farms[0]
    farm.update(money=5000, unlocked_quadrants=["NW", "NE", "SW"])
    cells = [(x, y) for y in range(5) for x in range(10) if (x, y) not in ((4, 4), (5, 4))]
    for index, (x, y) in enumerate(cells[:41]):
        farm.tiles[y][x] = game._new_plant("STRAWBERRY" if index < 34 else "WHEAT", 7, 24)
    candidate = get_last_callable(build())
    orders = candidate(deepcopy(obs), dict(env.configuration))["market"]
    purchases = [order for order in orders if order[0] == "BUY_SEED"]
    assert purchases == [["BUY_SEED", "WHEAT", 4]]
    initial = obs.private.seeds.get("WHEAT", 0)
    env.step([{"market": purchases, "farmer": ["PLANT", "WHEAT"]}, {}])
    assert env.state[0].observation.private.seeds["WHEAT"] == initial + 4
    assert env.state[0].observation.farms[0].tiles[4][4] is None
