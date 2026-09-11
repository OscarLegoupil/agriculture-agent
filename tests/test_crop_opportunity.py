"""Interpreter contracts for cohort yields, terminal sales and isolated admission changes."""

import hashlib
import json
import subprocess
import sys
from collections import Counter
from copy import deepcopy

import pytest
from experiments.crop_opportunity import INCUMBENT, build
from kaggle_environments import make
from kaggle_environments.agent import get_last_callable
from kaggle_environments.envs.kaggriculture import kaggriculture as game


def ns(mode="cohort", start_day=15):
    result = {}
    exec(build(mode, start_day), result)
    return result


def world(day=18, hour=0):
    env = make("kaggriculture", configuration={"seed": 5000})
    env.reset()
    obs = deepcopy(env.state[0].observation)
    obs.update(day=day, hour=hour, step=day * 24 + hour)
    obs["farms"][0]["money"] = 20000
    return obs, dict(env.configuration)


def test_exact_frozen_incumbent_and_last_callable():
    assert hashlib.sha256(build("incumbent").encode()).hexdigest() == INCUMBENT
    for mode in ("no_multiplier", "cohort"):
        assert get_last_callable(build(mode)).__name__ == "agent"


@pytest.mark.parametrize(
    "crop,born,fertilized",
    [
        ("WHEAT", 15, False),
        ("CARROT", 18, False),
        ("TOMATO", 18, True),
        ("TOMATO", 19, True),
        ("STRAWBERRY", 15, True),
        ("MELON", 15, False),
    ],
)
def test_projected_cohorts_match_official_growth_and_terminal_collections(crop, born, fertilized):
    sales, seeds, _, fertilizer_days = ns()["opportunity_schedule"](crop, born, fertilized)
    farm = dict(tiles=[[None]], farmer=[0, 0], hands=[])
    private = dict(shed={}, seeds={}, inventories=[{}])
    recorded = Counter()
    seed_dates = dict(seeds)
    for day in range(born, 30):
        if day in seed_dates:
            # Exhausted recurring crops are cleared before the modeled successor.
            if farm["tiles"][0][0] is not None:
                game._apply_unit_action(farm, private, 0, ["DIG"], 1, day, 24, 100)
            selected = crop if day == born or not game.CROPS[crop]["ongoing"] else "WHEAT"
            private["seeds"][selected] = 1
            game._apply_unit_action(farm, private, 0, ["PLANT", selected], 1, day, 24, 100)
        tile = farm["tiles"][0][0]
        if not isinstance(tile, dict) or tile.get("kind") != "PLANT":
            continue
        if day in fertilizer_days:
            private["inventories"][0]["FERTILIZER"] = 1
            game._apply_unit_action(farm, private, 0, ["FERTILIZE"], 1, day, 24, 100)
        game._apply_unit_action(farm, private, 0, ["WATER"], 1, day, 24, 100)
        spec = game.CROPS[tile["crop"]]
        age = day - tile["planted_day"]
        if (
            tile["yield_units"]
            and age >= spec["first_yield_day"]
            and (spec["ongoing"] or age >= spec["max_yield_day"] or day == 29)
        ):
            product = tile["crop"]
            game._apply_unit_action(farm, private, 0, ["HARVEST"], 1, day, 24, 100)
            recorded[min(29, day + 1), product] += private["inventories"][0].pop(product)
        game._daily_refresh_plants(farm, day, 24)
    expected = Counter()
    for day, item, units in sales:
        expected[day, item] += units
    assert recorded == expected
    assert all(day <= 29 for day, _, _ in sales)
    assert 29 not in fertilizer_days
    if crop == "TOMATO" and born == 18:
        assert sum(expected.values()) == 8
        assert expected[29, "TOMATO"] == 4


@pytest.mark.parametrize("start_day", [3, 15])
@pytest.mark.parametrize("seat", [0, 1])
def test_admission_start_preserves_earlier_policy_decisions(start_day, seat):
    obs, cfg = world(day=start_day - 1, hour=7)
    obs["farms"][seat] = deepcopy(obs["farms"][0])
    obs["player"] = seat
    obs["private"]["seeds"]["WHEAT"] = 2
    baseline = ns("incumbent")["agent"](deepcopy(obs), cfg)
    for mode in ("cohort", "no_multiplier"):
        assert ns(mode, start_day)["agent"](deepcopy(obs), cfg) == baseline


def test_floor_sales_pay_but_do_not_accumulate_market_supply():
    obs, _ = world()
    obs["market"]["prices"]["FERTILIZER"] = 40
    paths = {item: [11000.0] * 11 for item in game.PRODUCTS}
    arrivals = [dict.fromkeys(game.PRODUCTS, 0) for _ in range(30)]
    n = ns()
    a = n["crop_opportunity_values"](obs, n["PARAMS"], Counter(), paths, arrivals, (4, 4))
    b = n["crop_opportunity_values"](obs, n["PARAMS"], Counter(TOMATO=3), paths, arrivals, (4, 4))
    assert a["TOMATO"] == b["TOMATO"]
    farm = {"money": 0}
    private = {"shed": {"TOMATO": 1}}
    market = {"inventory": {"TOMATO": 11000}}
    assert game._commit_unit("SELL", "TOMATO", 1, farm, private, market)
    assert farm["money"] == 1 and market["inventory"]["TOMATO"] == 11000


def test_existing_seed_is_sunk_and_late_remote_planting_waits_for_next_day():
    obs, _ = world(day=18, hour=22)
    n = ns()
    paths = {item: [10000.0] * 11 for item in game.PRODUCTS}
    arrivals = [dict.fromkeys(game.PRODUCTS, 0) for _ in range(30)]
    target = (0, 0)
    empty = n["crop_opportunity_values"](obs, n["PARAMS"], Counter(), paths, arrivals, target)
    obs["private"]["seeds"]["TOMATO"] = 1
    held = n["crop_opportunity_values"](obs, n["PARAMS"], Counter(), paths, arrivals, target)
    assert held["TOMATO"] - empty["TOMATO"] == 50
    sales, *_ = n["opportunity_schedule"]("TOMATO", 19, False)
    assert sum(units for _, item, units in sales if item == "TOMATO") == 3


def test_cohort_results_are_immutable_and_cache_reuse_is_safe():
    n = ns()
    first = n["opportunity_schedule"]("TOMATO", 18, True)
    assert first == n["opportunity_schedule"]("TOMATO", 18, True)
    assert all(isinstance(part, tuple) for part in first)


def test_isolated_artifact_preserves_action_and_shed_inputs(tmp_path):
    source = build()
    obs, cfg = world()
    obs["private"]["shed"].update(WHEAT=12, FERTILIZER=3)
    before = deepcopy(obs)
    expected = get_last_callable(source)(obs, cfg)
    assert obs == before
    artifact = tmp_path / "main.py"
    artifact.write_text(source, encoding="utf-8")
    script = "import json,runpy,sys; n=runpy.run_path(sys.argv[1]); o,c=json.load(sys.stdin); print(json.dumps(n['agent'](o,c)))"
    result = subprocess.run(
        [sys.executable, "-I", "-S", "-c", script, str(artifact)],
        input=json.dumps([obs, cfg]),
        text=True,
        capture_output=True,
        check=True,
        cwd=tmp_path,
    )
    assert not result.stderr
    assert json.loads(result.stdout) == expected
