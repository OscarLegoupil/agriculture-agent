"""Official pricing rejects standalone arbitrage and exposes lockstep dependence."""

import json
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace

import pytest
from kaggle_environments import make
from kaggle_environments.envs.kaggriculture import kaggriculture as game
from kaggle_environments.utils import structify


def market_step(item, inventory, own_orders, other_orders=(), other_stock=0):
    env = make("kaggriculture", configuration={"seed": 5000})
    env.reset(2)
    raw = json.loads(json.dumps(env.state))
    raw[0]["observation"]["market"]["inventory"][item] = inventory
    for seat, orders in enumerate((own_orders, other_orders)):
        raw[0]["observation"]["farms"][seat]["money"] = 20000
        raw[seat]["observation"]["private"]["shed"] = {item: other_stock} if seat else {}
        raw[seat]["action"] = {"market": list(orders)}
    state = structify(raw)
    game._process_market(state, env)
    return state


@pytest.mark.parametrize("item", ["TOMATO", "CARROT"])
def test_steep_shortage_products_cannot_be_purchased(item):
    orders = [["BUY_PRODUCT", item, 50], ["SELL", item, 50]] * 5
    state = market_step(item, 0, orders)
    assert state[0].observation.farms[0]["money"] == 20000
    assert state[0].observation.private["shed"].get(item, 0) == 0
    assert state[0].observation.market["inventory"][item] == 0


@pytest.mark.parametrize("item", ["WHEAT", "FERTILIZER"])
@pytest.mark.parametrize("inventory", [9800, 11000])
def test_post_buy_quote_makes_five_standalone_cycles_cash_neutral(item, inventory):
    orders = [["BUY_PRODUCT", item, 50], ["SELL", item, 50]] * 5
    state = market_step(item, inventory, orders)
    assert state[0].observation.farms[0]["money"] == 20000
    assert state[0].observation.private["shed"].get(item, 0) == 0
    # Floor-price sales can remove market inventory, but do not generate cash.
    if game.market_price(item, inventory) > 1:
        assert state[0].observation.market["inventory"][item] == inventory


@pytest.mark.parametrize(
    "opponent,expected", [("PASS", 0), ("CYCLE", 50), ("BUY", 255), ("SELL", -245)]
)
def test_lockstep_cycle_profit_depends_on_unobserved_concurrent_orders(opponent, expected):
    own = [["BUY_PRODUCT", "FERTILIZER", 50], ["SELL", "FERTILIZER", 50]] * 5
    other = {
        "PASS": [],
        "CYCLE": own,
        "BUY": [["BUY_PRODUCT", "FERTILIZER", 50]],
        "SELL": [["SELL", "FERTILIZER", 50]],
    }[opponent]
    state = market_step("FERTILIZER", 9800, own, other, 50 if opponent == "SELL" else 0)
    assert state[0].observation.farms[0]["money"] - 20000 == expected
    assert state[0].observation.private["shed"].get("FERTILIZER", 0) == 0
    if opponent == "CYCLE":
        assert state[0].observation.farms[1]["money"] - 20000 == 50
        assert state[0].observation.market["inventory"]["FERTILIZER"] == 9800


REPLAY = Path(
    "reports/replays/breakthrough/"
    "fca083cdb5ac82dc4ad39a4227ef60ca57c948f819b565804aa706994f8e61ba-"
    "reference-mooman-main-5000-0.json"
)


@pytest.mark.skipif(not REPLAY.exists(), reason="Local replay is not distributed in CI")
def test_reachable_day16_cycle_needs_both_players_to_participate():
    replay = json.loads(REPLAY.read_bytes())
    raw = replay["steps"][384]
    before = [farm["money"] for farm in raw[0]["observation"]["farms"]]
    inventory = raw[0]["observation"]["market"]["inventory"]["FERTILIZER"]
    assert inventory == 10242
    for simultaneous in (False, True):
        state = deepcopy(raw)
        cycle = [["BUY_PRODUCT", "FERTILIZER", 25], ["SELL", "FERTILIZER", 25]] * 5
        state[0]["action"] = {"market": cycle}
        state[1]["action"] = {"market": cycle if simultaneous else []}
        state = structify(state)
        env = SimpleNamespace(configuration=structify(replay["configuration"]))
        game._process_market(state, env)
        changes = [
            farm["money"] - cash
            for farm, cash in zip(state[0].observation.farms, before, strict=True)
        ]
        assert changes == [25 if simultaneous else 0, 25 if simultaneous else 0]
        assert state[0].observation.market["inventory"]["FERTILIZER"] == inventory
