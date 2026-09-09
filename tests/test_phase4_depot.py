"""Spatial feed reserve respects official input timing and storage limits."""

import importlib
from copy import deepcopy
from pathlib import Path

import pytest
from kaggle_environments import make
from kaggle_environments.envs.kaggriculture import kaggriculture as game


@pytest.mark.parametrize("base", ["v8", "banked"])
def test_remote_feed_purchase_is_only_available_next_turn(monkeypatch, base):
    root = Path(__file__).resolve().parents[1]
    monkeypatch.chdir(root)
    monkeypatch.syspath_prepend(str(root / "scripts"))
    ns = {}
    exec(importlib.import_module("phase4_depot").build(base), ns)
    env = make("kaggriculture", configuration={"seed": 0})
    env.reset()
    obs = deepcopy(env.state[0].observation)
    obs.update(day=10, hour=10, step=250, player=0)
    farm = game._new_farm(10, 5000)
    farm.update(farmer=[4, 4], hands=[[0, 9]])
    farm["tiles"][4][5] = game._new_animal("COW", 0)
    farm["tiles"][3][4] = game._new_animal("SHEEP", 0)
    obs["farms"][0] = farm
    obs["private"] = {"shed": {}, "seeds": {}, "inventories": [{}, {"WHEAT": 6}]}

    def choose(state):
        return ns["agent"](deepcopy(state), dict(env.configuration))

    action = choose(obs)
    assert ["BUY_PRODUCT", "WHEAT", 2] in action["market"]
    assert action["farmer"][0] != "PICKUP"
    # An explicitly attempted pickup also fails before the market commits.
    attempted = deepcopy(obs)
    game._apply_unit_action(attempted["farms"][0], attempted["private"], 0,
                            ["PICKUP", "WHEAT", 2], 10, 10, 24, 100)
    assert not attempted["private"]["inventories"][0]
    env.state[0].observation = deepcopy(obs)
    env.state[0].action = {"market": [["BUY_PRODUCT", "WHEAT", 2]]}
    env.state[1].action = {"market": []}
    game._process_market(env.state, env)
    assert env.state[0].observation.private["shed"]["WHEAT"] == 2

    stocked = deepcopy(obs)
    stocked["private"]["shed"] = {"WHEAT": 3}
    market = choose(stocked)["market"]
    assert not any(o[:2] == ["BUY_PRODUCT", "WHEAT"] for o in market)
    assert sum(o[2] for o in market if o[:2] == ["SELL", "WHEAT"]) <= 1

    full = deepcopy(obs)
    full["private"]["shed"] = {"FERTILIZER": 88}
    full["private"]["inventories"][0] = {"MILK": 6}
    assert not any(o[:2] == ["BUY_PRODUCT", "WHEAT"] for o in choose(full)["market"])
    late = deepcopy(obs)
    late.update(hour=23, step=263)
    assert not any(o[:2] == ["BUY_PRODUCT", "WHEAT"] for o in choose(late)["market"])
