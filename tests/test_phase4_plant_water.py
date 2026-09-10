"""A fresh planting must receive its same-day watering before ordinary work."""

import importlib
from copy import deepcopy
from pathlib import Path

from kaggle_environments import make
from kaggle_environments.envs.kaggriculture import kaggriculture as game


def test_new_plant_water_reservation_survives_refresh_and_keeps_escape_first(monkeypatch):
    root = Path(__file__).resolve().parents[1]
    monkeypatch.chdir(root)
    monkeypatch.syspath_prepend(str(root / "scripts"))
    namespace = {}
    exec(importlib.import_module("phase4_plant_water").build(), namespace)
    env = make("kaggriculture", configuration={"seed": 0})
    env.reset()
    obs = deepcopy(env.state[0].observation)
    obs.update(day=11, hour=10, step=274, player=0)
    farm = game._new_farm(10, 15000)
    game._do_buy_land(farm, 10)
    farm["farmer"] = [4, 2]
    for row in farm["tiles"]:
        for x, tile in enumerate(row):
            if tile is None:
                row[x] = {"kind": "WEED"}
    fresh = game._new_plant("WHEAT", 11, 24)
    fresh["consecutive_unwatered"] = 1
    farm["tiles"][2][4] = fresh
    animal = game._new_animal("COW", 0)
    animal.update(fed_today=True, cared_today=False)
    farm["tiles"][2][5] = animal
    obs["farms"][0] = farm
    obs["private"] = {"shed": {}, "seeds": {}, "inventories": [{}]}

    action = namespace["agent"](deepcopy(obs), dict(env.configuration))["farmer"]
    assert action == ["WATER"]
    game._apply_unit_action(farm, obs["private"], 0, action, 10, 11, 24, 100)
    game._daily_refresh_plants(farm, 11, 24)
    assert farm["tiles"][2][4]["crop"] == "WHEAT"

    fresh = game._new_plant("WHEAT", 11, 24)
    fresh["consecutive_unwatered"] = 1
    farm["tiles"][2][4] = fresh
    starving = game._new_animal("SHEEP", 0)
    starving["consecutive_unfed"] = 1
    farm["tiles"][0][4] = starving
    obs.update(hour=21, step=285)
    obs["private"]["inventories"] = [{"WHEAT": 1}]
    assert namespace["agent"](deepcopy(obs), dict(env.configuration))["farmer"] == ["NORTH"]
