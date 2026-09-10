"""Expansion experiments retain working capital and the finite-season cutoff."""

import importlib
from copy import deepcopy
from pathlib import Path

import pytest
from kaggle_environments import make
from kaggle_environments.envs.kaggriculture import kaggriculture as game


@pytest.mark.parametrize("mode", ["land_only", "crop70", "crop70_hands14"])
def test_fourth_quadrant_has_funding_and_season_guards(monkeypatch, mode):
    root = Path(__file__).resolve().parents[1]
    monkeypatch.chdir(root)
    monkeypatch.syspath_prepend(str(root / "scripts"))
    ns = {}
    exec(importlib.import_module("phase4_land").build(mode), ns)
    env = make("kaggriculture", configuration={"seed": 0})
    env.reset()
    obs = deepcopy(env.state[0].observation)
    obs.update(day=12, hour=12, step=300, player=0)
    farm = game._new_farm(10, 20000)
    game._do_buy_land(farm, 10)
    game._do_buy_land(farm, 10)
    planted = 0
    for row in farm["tiles"]:
        for x, tile in enumerate(row):
            if tile is None and planted < 60:
                row[x] = game._new_plant("WHEAT", 10, 24)
                planted += 1
    assert planted == 60
    obs["farms"][0] = farm
    obs["private"] = {"shed": {}, "seeds": {}, "inventories": [{}]}

    def buys_land(cash, day=12):
        state = deepcopy(obs)
        state["farms"][0]["money"] = cash
        state.update(day=day, step=day * 24 + 12)
        return ["BUY_LAND"] in ns["agent"](state, dict(env.configuration))["market"]

    assert not buys_land(6000)
    assert buys_land(10000)
    assert not buys_land(10000, 15)
