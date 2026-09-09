"""Final simultaneous deliveries must fit the interpreter's market-order cap."""

from collections import Counter
from copy import deepcopy

import pytest
from kaggle_environments import make
from kaggle_environments.envs.kaggriculture import kaggriculture as game

from kaggriculture.agent.competitive import agent


def apply_orders(cargo, use_policy, order_limit, opponent_milk=0):
    env = make("kaggriculture", configuration={"seed": 0, "maxMarketOrdersPerTurn": order_limit})
    env.reset()
    obs = env.state[0].observation
    obs.update(day=29, hour=22, step=718, player=0)
    farm = obs.farms[0]
    farm["farmer"] = [4, 4]
    farm["hands"] = [[4, 4] for _ in range(len(cargo) - 1)]
    obs.private["inventories"] = deepcopy(cargo)
    amounts = sum((Counter(inv) for inv in cargo), Counter())
    expected = sum(
        game.market_price(item, obs.market["inventory"][item] + unit, obs.market.get("params"))
        for item, count in amounts.items()
        for unit in range(count)
    )
    initial_cash = farm["money"]
    opponent_cash = obs.farms[1]["money"]
    if use_policy:
        action = agent(obs, dict(env.configuration))
    else:
        action = {
            "farmer": ["DROP"],
            "hands": [["DROP"] for _ in farm["hands"]],
            "market": [
                ["SELL", item, count] for inv in reversed(cargo) for item, count in inv.items()
            ],
        }
    for idx, operation in enumerate([action["farmer"], *action["hands"]]):
        game._apply_unit_action(farm, obs.private, idx, operation, 10, 29, 24, 100)
    env.state[0].action = action
    env.state[1].action = {"farmer": ["PASS"], "hands": [], "market": []}
    if opponent_milk:
        env.state[1].observation.private["shed"]["MILK"] = opponent_milk
        env.state[1].action["market"] = [["SELL", "MILK", opponent_milk]]
    game._process_market(env.state, env)
    return {
        "cash": farm["money"] - initial_cash,
        "opponent_cash": obs.farms[1]["money"] - opponent_cash,
        "expected": expected,
        "shed": dict(obs.private["shed"]),
        "market": deepcopy(obs.market["inventory"]),
        "orders": action["market"],
    }


@pytest.mark.parametrize(
    "cargo", [[{"MILK": 1} for _ in range(13)], [{"MILK": 1, "WOOL": 1} for _ in range(13)]]
)
def test_terminal_sales_match_unlimited_split_orders(cargo):
    result = apply_orders(cargo, use_policy=True, order_limit=10)
    reference = apply_orders(cargo, use_policy=False, order_limit=40)
    assert result["cash"] == reference["cash"] == result["expected"]
    assert result["market"] == reference["market"]
    assert sum(result["shed"].values()) == 0
    assert len(result["orders"]) <= 10


def test_active_opponent_sale_batches_can_change_cash_allocation():
    cargo = [{"MILK": 1} for _ in range(13)]
    aggregated = apply_orders(cargo, use_policy=True, order_limit=10, opponent_milk=13)
    split = apply_orders(cargo, use_policy=False, order_limit=40, opponent_milk=13)
    assert aggregated["cash"] != split["cash"]
    # Both players quote before either unit commits, so batching can also
    # change total proceeds even when final market supply is identical.
    assert aggregated["opponent_cash"] != split["opponent_cash"]
    assert aggregated["market"] == split["market"]
    assert sum(aggregated["shed"].values()) == 0
