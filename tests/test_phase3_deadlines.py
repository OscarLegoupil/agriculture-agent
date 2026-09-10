"""Urgent feed acquisition is executable and respects shared shed inventory."""

import hashlib
import importlib
from copy import deepcopy
from pathlib import Path

from kaggle_environments import make
from kaggle_environments.envs.kaggriculture import kaggriculture as game


def test_feed_route_reserves_input_before_product_drop(monkeypatch):
    root = Path(__file__).resolve().parents[1]
    monkeypatch.chdir(root)
    monkeypatch.syspath_prepend(str(root / "scripts"))
    module = importlib.import_module("phase3_deadlines")
    content = module.build()
    assert (
        hashlib.sha256(content.encode()).hexdigest()
        == "298602f62772a7a523a4fb29fa0726a884526cb9e0b584f43ecd92f41f6fe1cf"
    )
    namespace = {}
    exec(content, namespace)
    env = make("kaggriculture", configuration={"seed": 0, "episodeSteps": 720})
    env.reset()
    obs = deepcopy(env.state[0].observation)
    obs.update(day=16, hour=14, step=16 * 24 + 14, player=0)
    farm = game._new_farm(10, 23000)
    game._do_buy_land(farm, 10)
    farm["farmer"] = [5, 4]
    farm["hands"] = [[5, 4]]
    farm["hires_today"] = 1
    targets = [(9, 0), (9, 1)]
    for x, y in targets:
        animal = game._new_animal("SHEEP", 8)
        animal["consecutive_unfed"] = 1
        farm["tiles"][y][x] = animal
    obs["farms"][0] = farm
    obs["private"] = {"shed": {"WHEAT": 2}, "seeds": {}, "inventories": [{"MILK": 6}, {}]}
    action = namespace["agent"](deepcopy(obs), dict(env.configuration))
    assert [action["farmer"], *action["hands"]] == [["PICKUP", "WHEAT", 1]] * 2
    for i, first in enumerate([action["farmer"], *action["hands"]]):
        game._apply_unit_action(farm, obs["private"], i, first, 10, 16, 24, 100)
    assert obs["private"]["shed"]["WHEAT"] == 0
    assert obs["private"]["inventories"][0]["MILK"] == 6
    for i, (_x, y) in enumerate(targets):
        route = [["EAST"]] * 4 + [["NORTH"]] * (4 - y) + [["FEED"]]
        assert 15 + len(route) <= 24
        for move in route:
            game._apply_unit_action(farm, obs["private"], i, move, 10, 16, 24, 100)
    game._daily_refresh_animals(farm, 16)
    assert all("animal" in farm["tiles"][y][x] for x, y in targets)
    # Reset the same public scenario with only one shared feed unit. A market
    # purchase in this action must not count as an immediately available input.
    scarce = deepcopy(obs)
    scarce["private"] = {"shed": {"WHEAT": 1}, "seeds": {}, "inventories": [{"MILK": 6}, {}]}
    scarce["farms"][0]["farmer"] = [5, 4]
    scarce["farms"][0]["hands"] = [[5, 4]]
    for x, y in targets:
        scarce["farms"][0]["tiles"][y][x].update(consecutive_unfed=1, fed_today=False)
    action = namespace["agent"](scarce, dict(env.configuration))
    pickups = [a for a in [action["farmer"], *action["hands"]] if a[:2] == ["PICKUP", "WHEAT"]]
    assert sum(a[2] for a in pickups) <= 1
