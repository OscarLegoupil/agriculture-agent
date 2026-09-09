"""A first unfed production eve can destroy care despite no escape risk."""

import importlib
from copy import deepcopy
from pathlib import Path

import pytest
from kaggle_environments import make
from kaggle_environments.envs.kaggriculture import kaggriculture as game


def test_banked_production_deadline_uses_current_legal_state(monkeypatch):
    root = Path(__file__).resolve().parents[1]
    monkeypatch.chdir(root)
    monkeypatch.syspath_prepend(str(root / "scripts"))
    build = importlib.import_module("phase4_care").build
    ns = {}
    exec(build("banked"), ns)
    env = make("kaggriculture", configuration={"seed": 0})
    env.reset()
    obs = deepcopy(env.state[0].observation)
    obs.update(day=8, hour=16, step=8 * 24 + 16, player=0)
    farm = game._new_farm(10, 23000)
    farm["farmer"] = [4, 4]
    animal = game._new_animal("SHEEP", 0)
    animal.update(consecutive_unfed=0, pending_care_bonus=3)
    farm["tiles"][0][4] = animal
    obs["farms"][0] = farm
    obs["private"] = {"shed": {}, "seeds": {}, "inventories": [{"WHEAT": 1, "MILK": 6}]}
    first = ns["agent"](deepcopy(obs), dict(env.configuration))["farmer"]
    assert first == ["NORTH"]
    lost_farm = deepcopy(farm)
    game._daily_refresh_animals(lost_farm, 8)
    assert lost_farm["tiles"][0][4]["yield_units"] == 1
    assert lost_farm["tiles"][0][4]["pending_care_bonus"] == 0
    for action in [["NORTH"]] * 4 + [["FEED"]]:
        game._apply_unit_action(farm, obs["private"], 0, action, 10, 8, 24, 100)
    game._daily_refresh_animals(farm, 8)
    assert farm["tiles"][0][4]["yield_units"] == 4
    assert obs["private"]["inventories"][0]["MILK"] == 6
    # No imminent production means the targeted version preserves normal DROP.
    obs["farms"][0]["farmer"] = [4, 4]
    obs["farms"][0]["tiles"][0][4] = game._new_animal("SHEEP", 0)
    obs["farms"][0]["tiles"][0][4]["pending_care_bonus"] = 3
    obs["private"]["inventories"] = [{"WHEAT": 1, "MILK": 6}]
    obs.update(day=7, step=7 * 24 + 16)
    assert ns["agent"](deepcopy(obs), dict(env.configuration))["farmer"] == ["DROP"]


@pytest.mark.parametrize("mode", ["daily", "banked"])
def test_escape_risk_precedes_new_healthy_animal_obligation(monkeypatch, mode):
    root = Path(__file__).resolve().parents[1]
    monkeypatch.chdir(root)
    monkeypatch.syspath_prepend(str(root / "scripts"))
    build = importlib.import_module("phase4_care").build
    env = make("kaggriculture", configuration={"seed": 0})
    env.reset()
    obs = deepcopy(env.state[0].observation)
    obs.update(day=8, hour=16, step=8 * 24 + 16, player=0)
    farm = game._new_farm(10, 23000)
    game._do_buy_land(farm, 10)
    farm["farmer"] = [4, 4]
    dying = game._new_animal("SHEEP", 0)
    dying.update(consecutive_unfed=1)
    healthy = game._new_animal("SHEEP", 0)
    healthy.update(pending_care_bonus=3)
    farm["tiles"][0][4] = dying
    farm["tiles"][0][7] = healthy
    obs["farms"][0] = farm
    obs["private"] = {"shed": {}, "seeds": {}, "inventories": [{"WHEAT": 1, "MILK": 6}]}
    choices = {}
    for priority in ["slack", "escape"]:
        ns = {}
        exec(build(mode, priority=priority), ns)
        choices[priority] = ns["agent"](deepcopy(obs), dict(env.configuration))["farmer"]
    assert choices == {"slack": ["EAST"], "escape": ["NORTH"]}
    for operation in [["NORTH"]] * 4 + [["FEED"]]:
        game._apply_unit_action(farm, obs["private"], 0, operation, 10, 8, 24, 100)
    game._daily_refresh_animals(farm, 8)
    assert "animal" in farm["tiles"][0][4]
    assert farm["tiles"][0][4]["consecutive_unfed"] == 0
