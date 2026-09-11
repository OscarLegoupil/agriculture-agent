"""A cheap hand can collect already available revenue before cash starvation."""

from copy import deepcopy

from experiments.startup_liquidity import build, startup_hire_reserve
from kaggle_environments import make
from kaggle_environments.agent import get_last_callable
from kaggle_environments.envs.kaggriculture import kaggriculture as game


def test_low_cash_hiring_is_legal_and_workers_arrive_after_this_action():
    env = make("kaggriculture", configuration={"seed": 5000})
    env.reset(2)
    obs = env.state[0].observation
    obs.update(day=1, hour=0, step=24)
    farm = obs.farms[0]
    farm.money = 39
    cow = game._new_animal("COW", 0)
    cow["fertilizer_available"] = True
    farm.tiles[3][4] = cow
    action = get_last_callable(build())(deepcopy(obs), dict(env.configuration))
    assert sum(order == ["HIRE"] for order in action["market"]) == 3
    assert not action["hands"]
    env.step([action, {}])
    assert len(env.state[0].observation.farms[0].hands) == 3
    assert env.state[0].observation.farms[0].money == 35
    assert env.state[0].observation.farms[0].tiles[3][4]["fertilizer_available"]


def test_uncollectable_or_future_revenue_does_not_relax_reserve():
    env = make("kaggriculture", configuration={"seed": 5000})
    env.reset(2)
    obs = env.state[0].observation
    obs.update(day=1, hour=0, step=24)
    obs.farms[0].tiles[3][4] = game._new_animal("COW", 0)
    assert startup_hire_reserve(obs, 0, 1) == 120
    obs.farms[0].tiles[3][4]["fertilizer_available"] = True
    assert startup_hire_reserve(obs, 0, 1) == 10
    assert startup_hire_reserve(obs, 3, 3) == 120
    obs.hour = 19
    assert startup_hire_reserve(obs, 0, 1) == 120
