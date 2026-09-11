"""Official transitions verify minimum watering without optional prerequisites."""

import gzip
import json
import subprocess
import sys
import time
from copy import deepcopy
from pathlib import Path

import pytest
from experiments.deadline_water import CONTROL, build
from kaggle_environments import make
from kaggle_environments.agent import get_last_callable
from kaggle_environments.envs.kaggriculture import kaggriculture as game

MARKET_SAFE = "a028706ed48d71983ea57522eedf9bed450341a8f2247b97281b8e2a7a4f28eb"


def namespace(source):
    result = {}
    exec(source, result)
    return result


def world(seat=0, *, hour=22):
    env = make("kaggriculture", configuration={"seed": 5018, "weedSpawnChance": 0})
    env.reset()
    obs = deepcopy(env._Environment__get_shared_state(seat).observation)
    obs.update(day=24, hour=hour, step=576 + hour, player=seat)
    farm = game._new_farm(10, 20000)
    game._do_buy_land(farm, 10)
    game._do_buy_land(farm, 10)
    farm["farmer"] = [8, 0]
    for y in (0, 1):
        crop = game._new_plant("STRAWBERRY", 9, 24)
        crop.update(yield_units=1, consecutive_unwatered=1)
        if y == 0:
            crop.update(watered_today=True, fertilized_until_day=26)
        farm["tiles"][y][8] = crop
    obs["farms"][seat] = farm
    obs["private"] = {"shed": {}, "seeds": {}, "inventories": [{"FERTILIZER": 1}]}
    obs["market"]["prices"].update(FERTILIZER=1, STRAWBERRY=40)
    return obs, dict(env.configuration)


def routes(ns, obs, cfg, tasks):
    farm, private = obs["farms"][obs["player"]], obs["private"]
    return ns["daily_routes"](
        obs,
        cfg,
        [tuple(farm["farmer"])],
        private["inventories"],
        dict(private["shed"]),
        dict(private["seeds"]),
        tasks,
        {(4, 4), (4, 5), (5, 4), (5, 5)},
        {},
        dict(obs["market"]["prices"]),
        0,
    )[0]


def irrigate(target):
    return [(target, "WATER", 115, None, None), (target, "FERTILIZE", 80, "FERTILIZER", None)]


@pytest.mark.parametrize("seat", [0, 1])
def test_last_two_turns_preempt_optional_harvest_and_fertilizer(seat):
    obs, cfg = world(seat)
    ns = namespace(build())
    ns["_DAILY_ROUTES"][seat] = {
        "day": 24,
        "step": 598,
        "plans": {
            0: {
                "ops": [((8, 0), "HARVEST", None)],
                "expected": {(8, 0): ("PLANT", "STRAWBERRY", 9)},
            }
        },
    }
    actions = []
    farm = obs["farms"][seat]
    for hour in (22, 23):
        obs.update(hour=hour, step=576 + hour)
        work = routes(ns, obs, cfg, irrigate((8, 1))).get(0, ["PASS"])
        actions.append(work)
        game._apply_unit_action(farm, obs["private"], 0, work, 10, 24, 24, 100)
    assert actions == [["SOUTH"], ["WATER"]]
    game._daily_refresh_plants(farm, 24, 24)
    assert farm["tiles"][1][8]["crop"] == "STRAWBERRY"
    assert farm["tiles"][1][8]["yield_units"] == 2
    assert farm["tiles"][0][8]["yield_units"] == 3
    assert obs["private"]["inventories"][0] == {"FERTILIZER": 1}
    assert not ns["_DAILY_ROUTE_STATS"]["unassigned_obligations"]


@pytest.mark.parametrize("base", [CONTROL, MARKET_SAFE])
def test_zero_held_yield_or_missing_optional_fertilizer_cannot_erase_water(base):
    obs, cfg = world(hour=20)
    farm = obs["farms"][0]
    farm["tiles"][0][8] = None
    farm["tiles"][1][8]["yield_units"] = 0
    obs["private"]["inventories"] = [{}]
    obs["market"]["inventory"]["STRAWBERRY"] = 10000
    game._refresh_prices(obs["market"])
    for x in range(10):
        rival = game._new_plant("STRAWBERRY", 9, 24)
        rival["yield_units"] = 4
        obs["farms"][1]["tiles"][0][x] = rival
    ns = namespace(build(base=base))
    for hour in (20, 21):
        obs.update(hour=hour, step=576 + hour)
        work = routes(ns, obs, cfg, irrigate((8, 1))).get(0, ["PASS"])
        game._apply_unit_action(farm, obs["private"], 0, work, 10, 24, 24, 100)
    assert farm["tiles"][1][8]["watered_today"]
    game._daily_refresh_plants(farm, 24, 24)
    assert farm["tiles"][1][8]["yield_units"] == 1


def test_emergency_water_preserves_other_critical_feed_and_water_routes():
    obs, cfg = world(hour=18)
    farm = obs["farms"][0]
    farm["tiles"][0][8] = None
    sheep = game._new_animal("SHEEP", 0)
    sheep.update(consecutive_unfed=1, fed_today=False, yield_units=2)
    farm["tiles"][0][9] = sheep
    obs["private"]["inventories"][0]["WHEAT"] = 1
    ns = namespace(build())
    ns["_DAILY_ROUTES"][0] = {
        "day": 24,
        "step": 594,
        "plans": {
            0: {
                "ops": [((9, 0), "FEED", None), ((9, 0), "CARE", None)],
                "expected": {(9, 0): ("ANIMAL", "SHEEP", 0)},
            }
        },
    }
    for hour in range(18, 24):
        obs.update(hour=hour, step=576 + hour)
        tasks = irrigate((8, 1)) if not farm["tiles"][1][8]["watered_today"] else []
        work = routes(ns, obs, cfg, tasks).get(0, ["PASS"])
        game._apply_unit_action(farm, obs["private"], 0, work, 10, 24, 24, 100)
    assert sheep["fed_today"] and farm["tiles"][1][8]["watered_today"]
    game._daily_refresh_animals(farm, 24)
    game._daily_refresh_plants(farm, 24, 24)
    assert farm["tiles"][0][9]["animal"] == "SHEEP"
    assert farm["tiles"][1][8]["crop"] == "STRAWBERRY"


def test_optional_fertilizer_returns_after_observed_water_acknowledgment():
    obs, cfg = world(hour=15)
    obs["farms"][0]["farmer"] = [8, 1]
    ns = namespace(build())
    first = routes(ns, obs, cfg, irrigate((8, 1)))[0]
    assert first == ["WATER"]
    game._apply_unit_action(obs["farms"][0], obs["private"], 0, first, 10, 24, 24, 100)
    obs.update(hour=16, step=592)
    second = routes(ns, obs, cfg, [((8, 1), "FERTILIZE", 80, "FERTILIZER", None)])[0]
    assert second == ["FERTILIZE"]
    game._apply_unit_action(obs["farms"][0], obs["private"], 0, second, 10, 24, 24, 100)
    assert obs["farms"][0]["tiles"][1][8]["fertilized_until_day"] >= 24


def test_official_loader_reused_process_and_cold_opening_parity():
    policy = get_last_callable(build())
    assert policy.__name__ == "agent"
    env = make("kaggriculture", configuration={"seed": 5000})
    env.reset()
    original = get_last_callable(
        gzip.decompress((Path("reports/sources") / f"{CONTROL}.py.gz").read_bytes()).decode()
    )
    for seat in (0, 1):
        obs = deepcopy(env._Environment__get_shared_state(seat).observation)
        expected = original(deepcopy(obs), env.configuration)
        assert policy(deepcopy(obs), env.configuration) == expected
        assert policy(deepcopy(obs), env.configuration) == expected


@pytest.mark.parametrize("base", [CONTROL, MARKET_SAFE])
def test_clean_artifact_source_parity_and_daily_reset(base, tmp_path):
    source = build(base=base)
    policy = get_last_callable(source)
    obs, cfg = world(hour=15)
    started = time.perf_counter()
    expected = policy(deepcopy(obs), cfg)
    assert time.perf_counter() - started < 0.15
    artifact = tmp_path / "main.py"
    artifact.write_text(source, encoding="utf-8")
    script = "import json,runpy,sys; ns=runpy.run_path(sys.argv[1]); o,c=json.load(sys.stdin); print(json.dumps(ns['agent'](o,c)))"
    result = subprocess.run(
        [sys.executable, "-I", "-c", script, str(artifact)],
        input=json.dumps([obs, cfg]),
        capture_output=True,
        text=True,
        check=True,
        cwd=tmp_path,
    )
    assert not result.stderr
    assert json.loads(result.stdout) == expected
    obs.update(day=25, hour=0, step=600)
    assert policy(deepcopy(obs), cfg) == get_last_callable(source)(deepcopy(obs), cfg)
