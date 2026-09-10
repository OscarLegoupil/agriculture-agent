"""Interpreter-backed regressions discovered during the second research cycle."""

from pathlib import Path

import pytest
from kaggle_environments import make
from kaggle_environments.envs.kaggriculture import kaggriculture as game


@pytest.fixture
def repaired(monkeypatch):
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[2] / "scripts"))
    from phase2_correctness import build

    namespace = {}
    exec(compile(build("liquidity"), "candidate.py", "exec"), namespace)
    return namespace["agent"]


def test_planting_day_counts_as_unwatered_and_requires_another_action(repaired):
    env = make("kaggriculture", configuration={"seed": 17})
    obs = env.reset(2)[0].observation
    obs.hour = 23
    obs.private.seeds["MELON"] = 1
    assert repaired(obs)["farmer"][0] not in ("PLANT", "DIG")
    farm = obs.farms[0]
    game._apply_unit_action(farm, obs.private, 0, ["PLANT", "MELON"], 10, 0, 24, 100)
    assert farm.tiles[4][4]["kind"] == "PLANT"
    game._daily_refresh_plants(farm, 0, 24)
    assert farm.tiles[4][4]["kind"] == "WEED"
    assert obs.private.seeds["MELON"] == 0


def test_affordable_partial_feed_prevents_all_or_nothing_purchase(repaired):
    env = make("kaggriculture", configuration={"seed": 17})
    obs = env.reset(2)[0].observation
    obs.farms[0].money = 80
    for x, y in ((3, 4), (4, 3), (2, 4), (4, 2)):
        obs.farms[0].tiles[y][x] = game._new_animal("COW", 0)
    purchases = [a for a in repaired(obs)["market"] if a[:2] == ["BUY_PRODUCT", "WHEAT"]]
    assert purchases == [["BUY_PRODUCT", "WHEAT", 2]]


def test_fertilizer_target_does_not_buy_beyond_protected_stock(repaired):
    env = make("kaggriculture", configuration={"seed": 17})
    obs = env.reset(2)[0].observation
    obs.day = 9
    obs.step = 216
    obs.farms[0].money = 5000
    obs.private.shed["FERTILIZER"] = 20
    for y in range(5):
        for x in range(5):
            obs.farms[0].tiles[y][x] = game._new_plant("STRAWBERRY", 0, 24)
    market = repaired(obs)["market"]
    assert not any(a[:2] == ["BUY_PRODUCT", "FERTILIZER"] for a in market)


def test_nightly_delivery_never_drops_away_from_shed(monkeypatch):
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[2] / "scripts"))
    from phase2_production import build

    namespace = {}
    exec(compile(build("recurring"), "candidate.py", "exec"), namespace)
    env = make("kaggriculture", configuration={"seed": 17})
    obs = env.reset(2)[0].observation
    obs.farms[0].farmer = [0, 0]
    obs.farms[0].money = 10000
    obs.private.inventories[0]["MILK"] = 10
    assert namespace["agent"](obs)["farmer"][0] != "DROP"
