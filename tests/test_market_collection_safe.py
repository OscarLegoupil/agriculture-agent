"""Official service transitions expose and prevent collection priority starvation."""

import hashlib
import time
from copy import deepcopy

import pytest
from experiments.investment_liquidity import build as investment_build
from experiments.market_collection import build as market_build
from experiments.market_collection_safe import apply_safe_priorities, build
from kaggle_environments import make
from kaggle_environments.agent import get_last_callable
from kaggle_environments.envs.kaggriculture import kaggriculture as game

ACCESS = {(4, 4), (4, 5), (5, 4), (5, 5)}
CROPS = ((0, 2), (1, 1), (2, 0), (0, 3))
ANIMALS = ((3, 4), (4, 3), (3, 3), (4, 2))


def world(seat=0, *, day=21, hour=17, workers=4):
    env = make("kaggriculture", configuration={"seed": 5000, "weedSpawnChance": 0})
    env.reset()
    obs = deepcopy(env._Environment__get_shared_state(seat).observation)
    obs.update(player=seat, day=day, hour=hour, step=day * 24 + hour)
    farm = game._new_farm(10, 20000)
    farm.update(farmer=[4, 4], hands=[[4, 4] for _ in range(workers - 1)])
    obs["farms"][seat] = farm
    obs["private"] = {"shed": {}, "seeds": {}, "inventories": [{} for _ in range(workers)]}
    for x, y in CROPS:
        plant = game._new_plant("TOMATO", day - 4, 24)
        plant.update(consecutive_unwatered=1, yield_units=0, watered_today=False)
        farm["tiles"][y][x] = plant
    for x, y in ANIMALS:
        animal = game._new_animal("SHEEP", day - 12)
        animal.update(yield_units=6, fed_today=True, cared_today=False)
        farm["tiles"][y][x] = animal
    for x in range(4):
        animal = game._new_animal("SHEEP", day - 12)
        animal["yield_units"] = 6
        obs["farms"][1 - seat]["tiles"][0][x] = animal
    obs["market"]["inventory"]["WOOL"] = 10040
    game._refresh_prices(obs["market"])
    return obs, dict(env.configuration)


def namespace(source):
    result = {}
    exec(source, result)
    return result


def tasks_for(obs):
    tasks = []
    farm = obs["farms"][obs["player"]]
    for y, row in enumerate(farm["tiles"]):
        for x, tile in enumerate(row):
            if not isinstance(tile, dict):
                continue
            if tile.get("kind") == "PLANT" and not tile["watered_today"]:
                tasks.append(((x, y), "WATER", 100, None, None))
            if "animal" in tile and not tile["fed_today"]:
                tasks.append(((x, y), "FEED", 100, "WHEAT", None))
            if tile.get("yield_units", 0):
                tasks.append(((x, y), "HARVEST", 70, None, None))
    return tasks


def dispatch(ns, obs, cfg, *, investment=0):
    farm, private = obs["farms"][obs["player"]], obs["private"]
    positions = [tuple(farm["farmer"]), *(tuple(pos) for pos in farm["hands"])]
    args = (
        obs,
        cfg,
        positions,
        private["inventories"],
        dict(private["shed"]),
        dict(private["seeds"]),
        tasks_for(obs),
        ACCESS,
        {},
        dict(obs["market"]["prices"], TOMATO=250),
        len(farm["hands"]),
    )
    if investment:
        args += (investment,)
    return ns["daily_routes"](*args)[0]


def finish_service_day(source, obs, cfg):
    ns = namespace(source)
    farm = obs["farms"][obs["player"]]
    history = []
    elapsed = []
    for hour in range(obs["hour"], 24):
        obs.update(hour=hour, step=obs["day"] * 24 + hour)
        start = time.perf_counter()
        actions = dispatch(ns, obs, cfg)
        elapsed.append(time.perf_counter() - start)
        history.append(actions)
        for worker in range(len(obs["private"]["inventories"])):
            game._apply_unit_action(
                farm,
                obs["private"],
                worker,
                actions.get(worker, ["PASS"]),
                10,
                obs["day"],
                24,
                cfg["shedCapacity"],
            )
    game._daily_refresh_plants(farm, obs["day"], 24)
    game._daily_refresh_animals(farm, obs["day"])
    return ns, history, elapsed


@pytest.mark.parametrize("seat", [0, 1])
def test_dense_farm_waters_before_rival_pressure_collection(seat):
    obs, cfg = world(seat)
    old_obs, safe_obs = deepcopy(obs), deepcopy(obs)
    old, old_actions, _ = finish_service_day(market_build(), old_obs, cfg)
    safe, actions, elapsed = finish_service_day(build(), safe_obs, cfg)
    old_tiles, tiles = old_obs["farms"][seat]["tiles"], safe_obs["farms"][seat]["tiles"]
    assert sum(old_tiles[y][x].get("kind") == "WEED" for x, y in CROPS) == 4
    assert all(tiles[y][x].get("crop") == "TOMATO" for x, y in CROPS)
    # The unsafe variant really harvests and delivers wool; the difference is
    # service precedence, not an illegal shortcut or synthetic income credit.
    assert old_obs["private"]["shed"].get("WOOL", 0) > 0
    assert any(["DROP"] in turn.values() for turn in old_actions)
    assert any(["WATER"] in turn.values() for turn in actions)
    assert not safe["_DAILY_ROUTE_STATS"]["unassigned_obligations"]
    assert not safe["_DAILY_ROUTE_STATS"]["budget_fallbacks"]
    assert old["_DAILY_ROUTE_STATS"]["unassigned_obligations"] > 0
    assert max(elapsed) < 0.15


def test_builder_is_deterministic_and_keeps_official_entrypoint():
    source = build()
    assert source == build()
    assert get_last_callable(source).__name__ == "agent"
    assert hashlib.sha256(market_build().encode()).hexdigest() == (
        "a283c29d5ac221d6eff14d23960f08ad09dd8797b8bcbbbf37407d873b01dc5f"
    )
    assert (
        get_last_callable(
            apply_safe_priorities(investment_build(), investment_pressure=True)
        ).__name__
        == "agent"
    )


def clear_farm(obs):
    board = obs["farms"][obs["player"]]["tiles"]
    for row in board:
        for x, tile in enumerate(row):
            if tile != "LOCKED":
                row[x] = None


def test_carried_wool_cannot_make_last_chance_watering_infeasible():
    obs, cfg = world(workers=1)
    clear_farm(obs)
    plant = game._new_plant("TOMATO", 17, 24)
    plant["consecutive_unwatered"] = 1
    obs["farms"][0]["tiles"][3][0] = plant
    obs["private"]["inventories"][0] = {"WOOL": 6}
    ns, history, _ = finish_service_day(build(), obs, cfg)
    assert obs["farms"][0]["tiles"][3][0]["crop"] == "TOMATO"
    assert any(actions.get(0) == ["WATER"] for actions in history)
    # Returning from this far cell cannot also fit today. Cargo remains real,
    # carried stock for a subsequent delivery; no virtual sale is credited.
    assert obs["private"]["inventories"][0]["WOOL"] == 6
    assert not obs["private"]["shed"]
    assert not ns["_DAILY_ROUTE_STATS"]["unassigned_obligations"]


@pytest.mark.parametrize("animal", [False, True])
def test_investment_collection_keeps_water_and_escape_feed_prerequisites(animal):
    obs, cfg = world(day=10, hour=1, workers=1)
    clear_farm(obs)
    farm = obs["farms"][0]
    farm["farmer"] = [4, 3]
    if animal:
        tile = game._new_animal("SHEEP", 0)
        tile.update(yield_units=6, consecutive_unfed=1, fed_today=False)
        obs["private"]["shed"]["WHEAT"] = 1
        prerequisite = "FEED"
    else:
        tile = game._new_plant("STRAWBERRY", 0, 24)
        tile.update(yield_units=3, consecutive_unwatered=1, watered_today=False)
        prerequisite = "WATER"
    farm["tiles"][3][4] = tile
    old, safe = (
        namespace(investment_build()),
        namespace(apply_safe_priorities(investment_build(), investment_pressure=True)),
    )
    dispatch(old, deepcopy(obs), cfg, investment=1)
    dispatch(safe, deepcopy(obs), cfg, investment=1)
    old_ops = [op for _, op, _ in old["_DAILY_ROUTES"][0]["plans"][0]["ops"]]
    safe_ops = [op for _, op, _ in safe["_DAILY_ROUTES"][0]["plans"][0]["ops"]]
    assert prerequisite not in old_ops
    assert safe_ops.index(prerequisite) < safe_ops.index("HARVEST")
    history = []
    for hour in range(1, 11):
        obs.update(hour=hour, step=240 + hour)
        action = dispatch(safe, obs, cfg, investment=1).get(0, ["PASS"])
        history.append(action[0])
        game._apply_unit_action(farm, obs["private"], 0, action, 10, 10, 24, 100)
    assert history.index(prerequisite) < history.index("HARVEST")
    assert tile["fed_today" if animal else "watered_today"]
    if animal:
        game._daily_refresh_animals(farm, 10)
        assert farm["tiles"][3][4]["animal"] == "SHEEP"
    else:
        game._daily_refresh_plants(farm, 10, 24)
        assert farm["tiles"][3][4]["crop"] == "STRAWBERRY"


def test_investment_cargo_preserves_retained_watering_then_real_delivery():
    obs, cfg = world(day=10, hour=1, workers=1)
    clear_farm(obs)
    plant = game._new_plant("TOMATO", 6, 24)
    plant["consecutive_unwatered"] = 1
    obs["farms"][0]["tiles"][2][0] = plant
    obs["private"]["inventories"][0] = {"WOOL": 6}
    ns = namespace(apply_safe_priorities(investment_build(), investment_pressure=True))
    ns["_DAILY_ROUTES"][0] = {
        "day": 10,
        "step": 241,
        "plans": {
            0: {"ops": [((0, 2), "WATER", None)], "expected": {(0, 2): ("PLANT", "TOMATO", 6)}}
        },
    }
    history = []
    for hour in range(1, 16):
        obs.update(hour=hour, step=240 + hour)
        action = dispatch(ns, obs, cfg, investment=1).get(0, ["PASS"])
        history.append(action[0])
        game._apply_unit_action(obs["farms"][0], obs["private"], 0, action, 10, 10, 24, 100)
    assert history.index("WATER") < history.index("DROP")
    assert plant["watered_today"]
    assert obs["private"]["shed"].get("WOOL") == 6


def test_melon_opening_race_and_cold_opening_decision_remain_unchanged():
    obs, cfg = world(day=10, hour=5, workers=1)
    clear_farm(obs)
    farm = obs["farms"][0]
    farm["farmer"] = [4, 2]
    melon = game._new_plant("MELON", 0, 24)
    melon.update(yield_units=6, watered_today=True)
    farm["tiles"][2][4] = melon
    old, new = get_last_callable(market_build()), get_last_callable(build())
    for hour in range(5, 9):
        obs.update(hour=hour, step=240 + hour)
        action = new(deepcopy(obs), cfg)
        assert action == old(deepcopy(obs), cfg)
        game._apply_unit_action(farm, obs["private"], 0, action["farmer"], 10, 10, 24, 100)
    assert action["farmer"] == ["DROP"]
    assert ["SELL", "MELON", 6] in action["market"]
    env = make("kaggriculture", configuration={"seed": 5000})
    env.reset()
    for seat in (0, 1):
        fresh = deepcopy(env._Environment__get_shared_state(seat).observation)
        expected = get_last_callable(market_build())(deepcopy(fresh), env.configuration)
        assert new(deepcopy(fresh), env.configuration) == expected
        assert new(deepcopy(fresh), env.configuration) == expected
