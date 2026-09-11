"""Interpreter contracts and deployment parity for the marginal labor prototype."""

import gzip
import json
from pathlib import Path

import pytest
from experiments.labor_calendar import INCUMBENT, build, daily_labor_work, labor_calendar_plan
from kaggle_environments import make
from kaggle_environments.agent import get_last_callable
from kaggle_environments.envs.kaggriculture import kaggriculture as game


def test_official_hire_costs_and_new_worker_action_availability():
    environment = make("kaggriculture", configuration={"seed": 5000, "farmHandCostMult": 3})
    environment.reset(2)
    initial_cash = environment.state[0].observation.farms[0].money
    environment.step(
        [
            {
                "farmer": ["PASS"],
                "hands": [["WEST"], ["NORTH"], ["NORTH"]],
                "market": [["HIRE"]] * 3,
            },
            {},
        ]
    )
    farm = environment.state[0].observation.farms[0]
    assert initial_cash - farm.money == 3 * (1 + 1 + 2)
    spawned = [tuple(position) for position in farm.hands]
    assert spawned == [(5, 4), (4, 5), (5, 5)]
    environment.step([{"hands": [["WEST"], ["NORTH"], ["NORTH"]], "market": [["HIRE"]]}, {}])
    farm = environment.state[0].observation.farms[0]
    assert initial_cash - farm.money == 3 * (1 + 1 + 2 + 3)
    assert [tuple(position) for position in farm.hands[:3]] == [(4, 4), (4, 4), (5, 4)]
    assert tuple(farm.hands[3]) == (4, 5)


def test_work_obligations_disappear_after_official_service():
    environment = make("kaggriculture", configuration={"seed": 5000})
    environment.reset(2)
    observation = environment.state[0].observation
    observation.update(day=18, hour=0, step=432)
    farm, private = observation.farms[0], observation.private
    farm.money = 0  # Isolate existing obligations from speculative commissioning.
    animal = game._new_animal("SHEEP", 10)
    animal.update(yield_units=3, fertilizer_available=True, consecutive_unfed=1)
    farm.tiles[4][4] = animal
    crop = game._new_plant("WHEAT", 16, 24)
    farm.tiles[4][3] = crop
    private.inventories[0]["WHEAT"] = 1
    before = daily_labor_work(observation, environment.configuration)
    assert before["operations"] == {
        "WATER": 1,
        "HARVEST": 2,
        "FEED": 1,
        "CARE": 1,
        "COLLECT_FERTILIZER": 1,
    }
    for action in (["FEED"], ["CARE"], ["COLLECT_FERTILIZER"], ["HARVEST"]):
        game._apply_unit_action(farm, private, 0, action, 10, 18, 24, 100)
    farm.farmer = [3, 4]
    game._apply_unit_action(farm, private, 0, ["WATER"], 10, 18, 24, 100)
    assert farm.tiles[4][3]["yield_units"] == 2
    game._apply_unit_action(farm, private, 0, ["HARVEST"], 10, 18, 24, 100)
    after = daily_labor_work(observation, environment.configuration)
    assert after["service_actions"] == 0
    assert after["urgent_actions"] == 0
    assert after["estimated_work"] < before["estimated_work"]


def test_increasing_official_wages_cannot_buy_more_identical_capacity():
    environment = make("kaggriculture", configuration={"seed": 5000})
    environment.reset(2)
    observation = environment.state[0].observation
    observation.update(day=20, hour=0, step=480)
    farm = observation.farms[0]
    farm.money = 10000
    for y in range(4):
        for x in range(4):
            animal = game._new_animal("SHEEP", 6)
            animal.update(yield_units=3, fertilizer_available=True)
            farm.tiles[y][x] = animal
    ordinary = labor_calendar_plan(observation, {"farmHandCostMult": 1})
    expensive = labor_calendar_plan(observation, {"farmHandCostMult": 100})
    assert expensive["target_hands"] < ordinary["target_hands"]
    official = game._new_farm(10, 100000)
    private = game._new_private()
    for decision in ordinary["marginal_hires"]:
        cash = official["money"]
        game._do_hire(official, private, 10)
        assert cash - official["money"] == decision["wage"]


def test_official_loader_selects_the_changed_policy_and_terminal_stays_identical():
    loaded = get_last_callable(build())
    namespace = {}
    exec(gzip.decompress(Path(f"reports/sources/{INCUMBENT}.py.gz").read_bytes()), namespace)
    assert loaded.__name__ == "agent"
    assert "labor_calendar_plan" in loaded.__code__.co_names
    environment = make("kaggriculture", configuration={"seed": 5000})
    environment.reset(2)
    observation = environment.state[0].observation
    for day, hour, step in ((0, 0, 0), (2, 7, 55), (29, 22, 718)):
        observation.update(day=day, hour=hour, step=step)
        assert loaded(observation, environment.configuration) == namespace["agent"](
            observation, environment.configuration
        )


@pytest.mark.parametrize("location", ["shed", "carried"])
def test_paid_animal_queue_retains_incumbent_commissioning_labor(location):
    environment = make("kaggriculture", configuration={"seed": 5000})
    environment.reset(2)
    observation = environment.state[0].observation
    observation.update(day=15, hour=0, step=360)
    observation.farms[0].money = 400
    inventory = (
        observation.private.shed if location == "shed" else observation.private.inventories[0]
    )
    inventory["COW"] = 1
    assert labor_calendar_plan(observation, environment.configuration)["target_hands"] < 4
    loaded = get_last_callable(build())
    incumbent = get_last_callable(
        gzip.decompress(Path(f"reports/sources/{INCUMBENT}.py.gz").read_bytes()).decode()
    )
    action = loaded(observation, environment.configuration)
    assert action == incumbent(observation, environment.configuration)
    assert action["market"].count(["HIRE"]) == 4


REPLAY = Path(f"reports/replays/breakthrough/{INCUMBENT}-reference-cok-main-5000-0.json")


@pytest.mark.skipif(
    not REPLAY.exists(), reason="Local diagnostic replay is not distributed with CI"
)
def test_saved_startup_action_parity_and_day_specific_labor():
    replay = json.loads(REPLAY.read_bytes())
    loaded = get_last_callable(build())
    incumbent = get_last_callable(
        gzip.decompress(Path(f"reports/sources/{INCUMBENT}.py.gz").read_bytes()).decode()
    )
    for step in replay["steps"][:360]:
        observation = step[0]["observation"]
        assert loaded(observation, replay["configuration"]) == incumbent(
            observation, replay["configuration"]
        )
    quiet = labor_calendar_plan(replay["steps"][17 * 24][0]["observation"], replay["configuration"])
    harvest = labor_calendar_plan(
        replay["steps"][19 * 24][0]["observation"], replay["configuration"]
    )
    assert quiet["operations"]["HARVEST"] < harvest["operations"]["HARVEST"]
    assert quiet["target_hands"] < harvest["target_hands"]
