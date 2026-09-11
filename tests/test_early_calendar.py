"""Consequential opening changes exercised through official observations/actions."""

import hashlib
from copy import deepcopy

import pytest
from experiments.early_calendar import build
from kaggle_environments import make
from kaggle_environments.agent import get_last_callable
from kaggle_environments.envs.kaggriculture import kaggriculture as game


def world(day=5, hour=10, hands=6):
    env = make("kaggriculture", configuration={"seed": 5000})
    env.reset()
    obs = deepcopy(env.state[0].observation)
    farm = game._new_farm(10, 5000)
    farm.update(farmer=[4, 4], hands=[[4, 4] for _ in range(hands)])
    obs.update(day=day, hour=hour, step=day * 24 + hour, player=0)
    obs["farms"][0] = farm
    obs["private"] = {"shed": {}, "seeds": {}, "inventories": [{} for _ in range(hands + 1)]}
    return obs, dict(env.configuration)


def test_disabled_experiment_preserves_common_budget_artifact():
    assert hashlib.sha256(build().encode()).hexdigest() == (
        "fca083cdb5ac82dc4ad39a4227ef60ca57c948f819b565804aa706994f8e61ba"
    )


@pytest.mark.parametrize("seat", [0, 1])
def test_early_herd_reserves_real_sites_and_buys_missing_cow(seat):
    obs, cfg = world(day=3, hour=10, hands=6)
    farm = obs["farms"][0]
    farm["money"] = 2000
    positions = [(x, y) for y in range(5) for x in range(5) if (x, y) != (4, 4)]
    for index, (x, y) in enumerate(positions[:23]):
        farm["tiles"][y][x] = (
            game._new_animal("COW" if index < 2 else "SHEEP", 0)
            if index < 4
            else game._new_plant("MELON", 0, 24)
        )
    if seat:
        obs["farms"].reverse()
        obs["player"] = 1
    control = get_last_callable(build())(deepcopy(obs), cfg)
    decision = get_last_callable(build(early_herd=True))(deepcopy(obs), cfg)
    assert ["BUY_ANIMAL", "COW", 1] in decision["market"]
    assert not any(order[0] == "BUY_SEED" for order in decision["market"])
    assert not any(order[0] == "BUY_ANIMAL" for order in control["market"])
    # The interpreter charges the actual purchased animal cost.
    before = farm["money"]
    game._commit_unit(
        "BUY_ANIMAL", "COW", game.ANIMALS["COW"]["cost"], farm, obs["private"], obs["market"]
    )
    assert before - farm["money"] == 400


def test_public_demand_can_change_the_early_cohort():
    obs, cfg = world(day=8, hour=10, hands=6)
    farm = obs["farms"][0]
    farm["money"] = 10000
    for x in range(4):
        farm["tiles"][0][x] = game._new_animal("COW", 0)
    for index in range(7):
        farm["tiles"][1 + index // 5][index % 5] = game._new_plant("WHEAT", 7, 24)
    # An observable market state with high tomato demand and saturated berries.
    obs["market"]["inventory"]["TOMATO"] = 8000
    obs["market"]["inventory"]["STRAWBERRY"] = 10000
    game._refresh_prices(obs["market"])
    old = get_last_callable(build())(deepcopy(obs), cfg)
    new = get_last_callable(build(adaptive_crops=True))(deepcopy(obs), cfg)
    assert any(order[:2] == ["BUY_SEED", "TOMATO"] for order in new["market"])
    assert any(order[:2] == ["BUY_SEED", "STRAWBERRY"] for order in old["market"])


def test_official_loader_uses_declared_policy():
    for options in (
        {"early_herd": True},
        {"adaptive_crops": True},
        {"early_herd": True, "adaptive_crops": True},
    ):
        source = build(**options)
        namespace = {}
        exec(source, namespace)
        assert get_last_callable(source).__code__ == namespace["agent"].__code__
