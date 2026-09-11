"""Official worker transitions validate the daily fleet's service contracts."""

import gzip
import hashlib
import json
import subprocess
import sys
from copy import deepcopy
from pathlib import Path

import pytest
from experiments.daily_routes import INCUMBENT, build
from kaggle_environments import make
from kaggle_environments.agent import get_last_callable
from kaggle_environments.envs.kaggriculture import kaggriculture as game
from kaggle_environments.utils import structify


def policy():
    namespace = {}
    exec(build(), namespace)
    return namespace


def test_default_builder_preserves_qualified_fleet_bytes():
    assert hashlib.sha256(build().encode()).hexdigest() == (
        "9400f9b0cdaa02d268ab9e234779d17013f2facf5f5517698bdfdb04671464b7"
    )


def test_mature_labor_ablation_changes_actual_hire_orders_only_after_day14():
    decisions = {}
    for day in (14, 15):
        for hands in (10, 12):
            obs, cfg = world(day=day, hour=0, hands=0)
            farm = obs["farms"][0]
            farm["money"] = 100000
            for y in range(10):
                for x in range(5):
                    farm["tiles"][y][x] = game._new_plant("STRAWBERRY", 4, 24)
            for y in range(8):
                farm["tiles"][y][4] = game._new_animal("COW", 0)
            decision = get_last_callable(build(mature_hands=hands))(obs, cfg)
            decisions[day, hands] = sum(order == ["HIRE"] for order in decision["market"])
    assert decisions[14, 10] == decisions[14, 12]
    # The official ten-order cap spreads hiring across turns. Reserve cash
    # and existing hands determine whether the policy requests the last pair.
    obs, cfg = world(day=15, hour=1, hands=10)
    farm = obs["farms"][0]
    farm["money"] = 100000
    for y in range(10):
        for x in range(5):
            farm["tiles"][y][x] = game._new_plant("STRAWBERRY", 4, 24)
    for y in range(8):
        farm["tiles"][y][4] = game._new_animal("COW", 0)
    old = get_last_callable(build())(deepcopy(obs), cfg)
    new = get_last_callable(build(mature_hands=10))(deepcopy(obs), cfg)
    assert sum(order == ["HIRE"] for order in old["market"]) == 2
    assert all(order != ["HIRE"] for order in new["market"])


def test_cereal_rotation_orders_commercial_seed_after_financed_berry_cohort():
    obs, cfg = world(day=10, hour=0, hands=12)
    farm = obs["farms"][0]
    farm["money"] = 100000
    spaces = [(x, y) for y in range(10) for x in range(5) if (x, y) != (4, 4)]
    for index, (x, y) in enumerate(spaces):
        farm["tiles"][y][x] = (
            game._new_plant("STRAWBERRY", 4, 24)
            if index < 34
            else game._new_plant("WHEAT", 9, 24)
            if index < 41
            else game._new_animal("COW", 0)
            if index < 45
            else None
        )
    old = get_last_callable(build())(deepcopy(obs), cfg)
    new = get_last_callable(build(cereal=True))(deepcopy(obs), cfg)
    assert any(order[:2] == ["BUY_SEED", "STRAWBERRY"] for order in old["market"])
    assert any(order[:2] == ["BUY_SEED", "WHEAT"] for order in new["market"])
    assert not any(order[:2] == ["BUY_SEED", "STRAWBERRY"] for order in new["market"])


def world(day=5, hour=10, hands=1):
    env = make("kaggriculture", configuration={"seed": 0})
    env.reset()
    obs = deepcopy(env.state[0].observation)
    farm = game._new_farm(10, 5000)
    farm.update(farmer=[4, 4], hands=[[4, 5] for _ in range(hands)])
    obs.update(day=day, hour=hour, step=day * 24 + hour, player=0)
    obs["farms"][0] = farm
    obs["private"] = {"shed": {}, "seeds": {}, "inventories": [{} for _ in range(hands + 1)]}
    return obs, dict(env.configuration)


def run_units(namespace, obs, cfg, end=24):
    history = []
    for hour in range(obs["hour"], end):
        obs.update(hour=hour, step=obs["day"] * 24 + hour)
        action = namespace["agent"](deepcopy(obs), cfg)
        history.append(action)
        for worker, work in enumerate([action["farmer"], *action["hands"]]):
            game._apply_unit_action(
                obs["farms"][0], obs["private"], worker, work, 10, obs["day"], 24, 100
            )
    return history


@pytest.mark.parametrize("initial_inputs", [{"WHEAT": 2, "FERTILIZER": 1}, {}])
def test_joint_crop_and_animal_day_meets_all_production_prerequisites(initial_inputs):
    obs, cfg = world()
    farm = obs["farms"][0]
    for x in (3, 4):
        animal = game._new_animal("SHEEP", 0)
        animal.update(pending_care_bonus=3, fertilizer_available=True)
        farm["tiles"][1][x] = animal
        crop = game._new_plant("WHEAT", 1, 24)
        crop.update(yield_units=3)
        farm["tiles"][2][x] = crop
    berry = game._new_plant("STRAWBERRY", -4, 24)
    berry.update(consecutive_unwatered=1)
    farm["tiles"][3][3] = berry
    obs["private"]["shed"] = dict(initial_inputs)
    obs["market"]["prices"].update(FERTILIZER=10, STRAWBERRY=160, WOOL=200)
    ns = policy()
    history = run_units(ns, obs, cfg)
    assert all(farm["tiles"][1][x]["fed_today"] for x in (3, 4))
    assert all(farm["tiles"][1][x]["cared_today"] for x in (3, 4))
    assert all(farm["tiles"][2][x] is None for x in (3, 4))
    assert berry["watered_today"] and berry["fertilized_until_day"] >= 5
    wheat = obs["private"]["shed"].get("WHEAT", 0) + sum(
        inv.get("WHEAT", 0) for inv in obs["private"]["inventories"]
    )
    assert wheat == 6 + initial_inputs.get("WHEAT", 0)
    game._daily_refresh_animals(farm, 5)
    game._daily_refresh_plants(farm, 5, 24)
    assert sum(farm["tiles"][1][x]["yield_units"] for x in (3, 4)) == 8
    assert berry["yield_units"] == 2
    requested = [work for action in history for work in [action["farmer"], *action["hands"]]]
    assert sum(work[0] == "HARVEST" for work in requested) == 2
    assert sum(
        work[2] for work in requested if work[:2] == ["PICKUP", "WHEAT"]
    ) <= initial_inputs.get("WHEAT", 0)
    assert not ns["_DAILY_ROUTE_STATS"]["budget_fallbacks"]


def test_two_seed_reservations_cover_walking_workers_and_plant_day_water():
    obs, cfg = world(day=0, hour=0, hands=3)
    obs["private"]["seeds"] = {"MELON": 2}
    ns = policy()
    history = run_units(ns, obs, cfg, end=8)
    planted = [
        tile
        for row in obs["farms"][0]["tiles"]
        for tile in row
        if isinstance(tile, dict) and tile.get("kind") == "PLANT"
    ]
    assert len(planted) == 2
    assert all(tile["crop"] == "MELON" and tile["watered_today"] for tile in planted)
    assert (
        sum(
            work[0] == "PLANT"
            for action in history
            for work in [action["farmer"], *action["hands"]]
        )
        == 2
    )
    game._daily_refresh_plants(obs["farms"][0], 0, 24)
    assert all(tile["consecutive_unwatered"] == 0 for tile in planted)


def test_new_animal_can_be_commissioned_before_first_feed_purchase():
    obs, cfg = world(day=0, hour=0, hands=0)
    obs["private"]["shed"] = {"COW": 1}
    ns = policy()
    run_units(ns, obs, cfg, end=6)
    animals = [
        tile
        for row in obs["farms"][0]["tiles"]
        for tile in row
        if isinstance(tile, dict) and "animal" in tile
    ]
    assert len(animals) == 1
    assert obs["private"]["shed"].get("COW", 0) == 0


def test_terminal_harvest_includes_real_delivery_and_same_turn_sale():
    obs, cfg = world(day=29, hour=18, hands=0)
    farm = obs["farms"][0]
    farm["farmer"] = [4, 2]
    crop = game._new_plant("CARROT", 26, 24)
    crop.update(yield_units=3, watered_today=True)
    farm["tiles"][2][4] = crop
    ns = policy()
    history = run_units(ns, obs, cfg, end=23)
    assert farm["tiles"][2][4] is None
    assert not obs["private"]["inventories"][0]
    assert obs["private"]["shed"].get("CARROT", 0) == 3
    assert any(
        ["SELL", "CARROT", 3] in action["market"] and action["farmer"] == ["DROP"]
        for action in history
    )


def test_melon_delivery_is_prompt_despite_cash_and_unrelated_service():
    obs, cfg = world(day=10, hour=5, hands=0)
    farm = obs["farms"][0]
    farm["farmer"] = [4, 2]
    melon = game._new_plant("MELON", 0, 24)
    melon.update(yield_units=6, watered_today=True)
    farm["tiles"][2][4] = melon
    sheep = game._new_animal("SHEEP", 0)
    sheep.update(fed_today=True, fertilizer_available=True)
    farm["tiles"][2][3] = sheep
    ns = policy()
    history = run_units(ns, obs, cfg, end=9)
    assert [action["farmer"] for action in history] == [["HARVEST"], ["SOUTH"], ["SOUTH"], ["DROP"]]
    assert ["SELL", "MELON", 6] in history[-1]["market"]
    assert not obs["private"]["inventories"][0]


@pytest.mark.parametrize("player", [0, 1])
def test_reused_process_daily_reset_matches_fresh_policy(player):
    obs, cfg = world(day=0, hour=0, hands=2)
    if player:
        obs["farms"][1] = deepcopy(obs["farms"][0])
        obs["player"] = 1
    obs["private"]["seeds"] = {"MELON": 2}
    ns = policy()
    ns["agent"](deepcopy(obs), cfg)
    restarted = deepcopy(obs)
    restarted.update(day=1, step=24)
    assert ns["agent"](deepcopy(restarted), cfg) == policy()["agent"](deepcopy(restarted), cfg)
    assert ns["agent"](deepcopy(restarted), cfg) == ns["agent"](deepcopy(restarted), cfg)


def test_removed_animal_releases_a_committed_feed_obligation():
    obs, cfg = world(hour=10, hands=0)
    sheep = game._new_animal("SHEEP", 0)
    sheep.update(pending_care_bonus=3)
    obs["farms"][0]["tiles"][1][4] = sheep
    obs["private"]["shed"] = {"WHEAT": 1}
    ns = policy()
    run_units(ns, obs, cfg, end=11)
    obs["farms"][0]["tiles"][1][4] = {"kind": "PASTURE"}
    obs.update(hour=11, step=131)
    ns["agent"](deepcopy(obs), cfg)
    assert not any(
        op == "FEED" and target == (4, 1)
        for plan in ns["_DAILY_ROUTES"][0]["plans"].values()
        for target, op, _ in plan["ops"]
    )


@pytest.mark.parametrize("animal", [False, True])
def test_walking_before_dig_preserves_creation_prerequisites(animal):
    obs, cfg = world(day=0, hour=0, hands=0)
    farm = obs["farms"][0]
    farm["farmer"] = [0, 0]
    for row in farm["tiles"]:
        for x in range(len(row)):
            row[x] = "LOCKED"
    farm["tiles"][4][4] = {"kind": "WEED"}
    if animal:
        obs["private"]["shed"] = {"COW": 1}
    else:
        obs["private"]["seeds"] = {"WHEAT": 1}
    ns = policy()
    history = run_units(ns, obs, cfg, end=16)
    tile = farm["tiles"][4][4]
    if animal:
        assert tile.get("animal") == "COW"
        assert sum(action["farmer"][0] == "PLACE" for action in history) == 1
    else:
        assert tile.get("crop") == "WHEAT" and tile["watered_today"]
        assert sum(action["farmer"][0] == "PLANT" for action in history) == 1


def test_zero_current_yield_does_not_remove_harvest_behind_water():
    obs, cfg = world(day=5, hour=0, hands=0)
    farm = obs["farms"][0]
    crop = game._new_plant("WHEAT", 1, 24)
    crop.update(yield_units=0)
    farm["tiles"][2][4] = crop
    ns = policy()
    ns["_DAILY_ROUTES"][0] = {
        "day": 5,
        "step": 120,
        "plans": {
            0: {
                "ops": [((4, 2), "WATER", None), ((4, 2), "HARVEST", None)],
                "expected": {(4, 2): ("PLANT", "WHEAT", 1)},
            }
        },
    }
    history = run_units(ns, obs, cfg, end=5)
    assert [action["farmer"][0] for action in history[:4]] == ["NORTH", "NORTH", "WATER", "HARVEST"]
    assert farm["tiles"][2][4] is None
    assert obs["private"]["inventories"][0].get("WHEAT") == 1


def test_manure_cash_recovery_precedes_unfunded_service_and_new_investment():
    obs, cfg = world(day=1, hour=0, hands=0)
    farm = obs["farms"][0]
    farm["money"] = 39
    cow = game._new_animal("COW", 0)
    cow.update(fertilizer_available=True)
    farm["tiles"][4][4] = cow
    obs["private"]["shed"] = {"SHEEP": 1}
    obs["private"]["seeds"] = {"MELON": 4}
    ns = policy()
    env = make("kaggriculture", configuration={"seed": 5000})
    env.reset()
    env.state[0].observation = structify(obs)
    history = []
    for hour in range(5):
        current = env.state[0].observation
        current.update(day=1, hour=hour, step=24 + hour)
        decision = ns["agent"](deepcopy(current), cfg)
        history.append(decision)
        for worker, action in enumerate([decision["farmer"], *decision["hands"]]):
            game._apply_unit_action(
                current["farms"][0], current["private"], worker, action, 10, 1, 24, 100
            )
        env.state[0].action = decision
        env.state[1].action = {}
        game._process_market(env.state, env)
    assert history[0]["farmer"] == ["COLLECT_FERTILIZER"]
    assert history[1]["farmer"] == ["DROP"]
    assert any(order[:2] == ["SELL", "FERTILIZER"] for order in history[2]["market"])
    assert any(order == ["HIRE"] for decision in history[3:] for order in decision["market"])
    assert env.state[0].observation["farms"][0]["hands"]


def test_hiring_boundary_does_not_interrupt_manure_delivery_with_irrigation():
    obs, cfg = world(day=2, hour=3, hands=0)
    farm = obs["farms"][0]
    farm.update(money=121, farmer=[4, 3])
    for y, animal in enumerate(("SHEEP", "SHEEP", "COW", "COW"), start=1):
        tile = game._new_animal(animal, 0)
        tile.update(fertilizer_available=True)
        farm["tiles"][y][4] = tile
    for y in range(4):
        for x in range(3):
            crop = game._new_plant("MELON", 0, 24)
            crop.update(consecutive_unwatered=1)
            farm["tiles"][y][x] = crop
    obs["private"]["shed"] = {"WHEAT": 3}
    ns = policy()
    env = make("kaggriculture", configuration={"seed": 5000})
    env.reset()
    env.state[0].observation = structify(obs)
    history = []
    for hour in range(3, 8):
        current = env.state[0].observation
        current.update(day=2, hour=hour, step=48 + hour)
        decision = ns["agent"](deepcopy(current), cfg)
        history.append(decision)
        for worker, action in enumerate([decision["farmer"], *decision["hands"]]):
            game._apply_unit_action(
                current["farms"][0], current["private"], worker, action, 10, 2, 24, 100
            )
        env.state[0].action = decision
        env.state[1].action = {}
        game._process_market(env.state, env)
    assert [decision["farmer"] for decision in history[:3]] == [
        ["COLLECT_FERTILIZER"],
        ["SOUTH"],
        ["DROP"],
    ]
    assert any(order == ["HIRE"] for order in history[-1]["market"])
    assert len(env.state[0].observation["farms"][0]["hands"]) >= 5


def test_first_three_days_recover_labor_without_crop_deaths():
    """Official startup transitions, with an active frozen opponent in both runs."""
    root = Path(__file__).resolve().parents[1]
    incumbent = gzip.decompress(
        (root / "reports/sources" / f"{INCUMBENT}.py.gz").read_bytes()
    ).decode()
    results = {}
    for name, source in (("incumbent", incumbent), ("routes", build())):
        own, opponent = get_last_callable(source), get_last_callable(incumbent)
        env = make("kaggriculture", configuration={"seed": 5000})
        env.reset()
        deaths, labor = 0, {}
        for _ in range(72):
            views = [env._Environment__get_shared_state(player).observation for player in (0, 1)]
            before = deepcopy(views[0]["farms"][0]["tiles"])
            env.step([own(views[0], env.configuration), opponent(views[1], env.configuration)])
            current = env._Environment__get_shared_state(0).observation
            farm = current["farms"][0]
            if current["hour"] == 8:
                labor[current["day"]] = len(farm["hands"])
            for y, row in enumerate(farm["tiles"]):
                for x, tile in enumerate(row):
                    previous = before[y][x]
                    deaths += int(
                        isinstance(previous, dict)
                        and previous.get("kind") == "PLANT"
                        and isinstance(tile, dict)
                        and tile.get("kind") == "WEED"
                    )
        animals = sum(
            isinstance(tile, dict) and "animal" in tile for row in farm["tiles"] for tile in row
        )
        melons = sum(
            isinstance(tile, dict) and tile.get("crop") == "MELON"
            for row in farm["tiles"]
            for tile in row
        )
        results[name] = dict(deaths=deaths, labor=labor, animals=animals, melons=melons)
    assert results["routes"]["deaths"] == results["incumbent"]["deaths"] == 0
    assert results["routes"]["animals"] >= 4
    assert results["routes"]["melons"] >= 12
    assert all(results["routes"]["labor"][day] >= 5 for day in (1, 2))


def test_official_loader_and_isolated_artifact_have_identical_actions(tmp_path):
    source = build()
    loaded = get_last_callable(source)
    assert loaded.__name__ == "agent"
    obs, cfg = world(day=0, hour=0, hands=2)
    obs["private"]["seeds"] = {"MELON": 2}
    expected = loaded(deepcopy(obs), cfg)
    artifact = tmp_path / "main.py"
    artifact.write_text(source, encoding="utf-8")
    script = "import json,runpy,sys; ns=runpy.run_path(sys.argv[1]); obs,cfg=json.load(sys.stdin); print(json.dumps(ns['agent'](obs,cfg)))"
    result = subprocess.run(
        [sys.executable, "-I", "-c", script, str(artifact)],
        input=json.dumps([obs, cfg]),
        text=True,
        capture_output=True,
        check=True,
        cwd=tmp_path,
    )
    assert not result.stderr
    assert json.loads(result.stdout) == expected
