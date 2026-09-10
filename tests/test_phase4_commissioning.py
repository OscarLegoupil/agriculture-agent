"""Funded planting must retain watering and urgent animal-service feasibility."""

import importlib
from copy import deepcopy
from pathlib import Path

from kaggle_environments import make
from kaggle_environments.envs.kaggriculture import kaggriculture as game


def test_commissioning_replans_water_and_preserves_escape_deadline(monkeypatch):
    root = Path(__file__).resolve().parents[1]
    monkeypatch.chdir(root)
    monkeypatch.syspath_prepend(str(root / "scripts"))
    ns = {}
    exec(importlib.import_module("phase4_commissioning").build(), ns)
    env = make("kaggriculture", configuration={"seed": 0})
    env.reset()
    obs = deepcopy(env.state[0].observation)
    obs.update(day=11, hour=7, step=271, player=0)
    farm = game._new_farm(10, 15000)
    game._do_buy_land(farm, 10)
    farm["farmer"] = [4, 2]
    for row in farm["tiles"]:
        for x, tile in enumerate(row):
            if tile is None:
                row[x] = {"kind": "WEED"}
    farm["tiles"][2][4] = None
    animal = game._new_animal("COW", 0)
    animal.update(fed_today=True, cared_today=True, manure=1)
    farm["tiles"][2][5] = animal
    obs["farms"][0] = farm
    obs["private"] = {"shed": {}, "seeds": {"WHEAT": 1, "STRAWBERRY": 1}, "inventories": [{}]}
    for expected in [["PLANT", "WHEAT"], ["WATER"]]:
        action = ns["agent"](deepcopy(obs), dict(env.configuration))["farmer"]
        assert action == expected
        game._apply_unit_action(farm, obs["private"], 0, action, 10, 11, 24, 100)
        obs["hour"] += 1
        obs["step"] += 1
    game._daily_refresh_plants(farm, 11, 24)
    assert farm["tiles"][2][4]["crop"] == "WHEAT"
    farm["tiles"][2][4] = None
    dying = game._new_animal("SHEEP", 0)
    dying["consecutive_unfed"] = 1
    farm["tiles"][0][4] = dying
    obs["private"]["seeds"]["WHEAT"] = 1
    obs["private"]["inventories"] = [{"WHEAT": 1}]
    obs.update(hour=21, step=285)
    assert ns["agent"](deepcopy(obs), dict(env.configuration))["farmer"] == ["NORTH"]
    obs.update(hour=23, step=287)
    assert ns["agent"](deepcopy(obs), dict(env.configuration))["farmer"][0] != "PLANT"
