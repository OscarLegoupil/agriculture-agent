"""Sale scheduling contracts and an official market counterfactual."""

import itertools

from experiments.market_dispatch import build, dispatch_curve

from kaggriculture.agent.competitive import default_price_parameters, inventory_quote


def test_quantity_dp_matches_exhaustive_schedules_with_own_price_impact():
    spec = default_price_parameters()["WOOL"]
    inventories = [10030, 10005, 9980]
    units = 9
    best = -1
    first = None
    for early, middle in itertools.product(range(units + 1), repeat=2):
        if early + middle > units:
            continue
        sold = 0
        value = 0
        for day, amount in enumerate((early, middle, units - early - middle)):
            value += sum(
                inventory_quote(inventories[day] + sold + k, spec) for k in range(amount)
            ) / (1 + 0.025 * day)
            sold += amount
        if value > best:
            best, first = value, early
    amount, value = dispatch_curve(inventories, spec, units, inventory_quote)
    assert amount == first
    assert abs(value - best) < 1e-8


def test_sale_curve_matches_official_interleaved_unit_execution():
    from kaggle_environments import make
    from kaggle_environments.envs.kaggriculture import kaggriculture as game

    env = make("kaggriculture", configuration={"seed": 5000})
    env.reset(2)
    obs = env.state[0].observation
    obs["market"]["inventory"]["WOOL"] = 10030
    game._refresh_prices(obs["market"])
    obs.private.shed["WOOL"] = 9
    cash = obs.farms[0].money
    expected = sum(inventory_quote(10030 + k, default_price_parameters()["WOOL"]) for k in range(9))
    env.step([{"market": [["SELL", "WOOL", 9]]}, {}])
    assert env.state[0].observation.farms[0].money - cash == expected


def test_budget_fallback_is_immediate_valid_liquidation(capsys):
    spec = default_price_parameters()["WOOL"]
    amount, value = dispatch_curve([10050, 9900], spec, 10, inventory_quote, deadline=0)
    assert amount == 10
    assert value == sum(inventory_quote(10050 + k, spec) for k in range(10))
    assert "budget_fallback" in capsys.readouterr().err


def test_deployment_entry_point_and_terminal_liquidation():
    from kaggle_environments import make

    namespace = {}
    exec(build(), namespace)
    env = make("kaggriculture", configuration={"seed": 5000})
    env.reset(2)
    obs = env.state[0].observation
    obs.update(day=29, hour=22, step=718)
    obs.private.shed["WOOL"] = 9
    action = namespace["agent"](obs, env.configuration)
    assert ["SELL", "WOOL", 9] in action["market"]
