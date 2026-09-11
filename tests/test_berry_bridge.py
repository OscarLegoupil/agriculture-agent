"""Official transitions verify the financed cohort and worker-arrival ablation."""

import hashlib
import json
import subprocess
import sys
from collections import Counter
from copy import deepcopy

import pytest
from experiments.berry_bridge import FLEET, build
from experiments.daily_routes import build as fleet_build
from kaggle_environments import make
from kaggle_environments.agent import get_last_callable
from kaggle_environments.envs.kaggriculture import kaggriculture as game


def world(day=5, hour=0, hands=0):
    env = make("kaggriculture", configuration={"seed": 5000})
    env.reset()
    obs = deepcopy(env.state[0].observation)
    farm = game._new_farm(10, 5000)
    farm.update(farmer=[4, 4], hands=[[4, 4] for _ in range(hands)])
    obs.update(player=0, day=day, hour=hour, step=day * 24 + hour)
    obs["farms"][0] = farm
    obs["private"] = {"shed": {}, "seeds": {}, "inventories": [{} for _ in range(hands + 1)]}
    return obs, dict(env.configuration)


def namespace(**options):
    result = {}
    exec(build(**options), result)
    return result


@pytest.mark.parametrize("cereal", [False, True])
def test_disabled_bridge_preserves_exact_base(cereal):
    source = build(berries=0, cereal=cereal)
    assert source == fleet_build(cereal=cereal)
    if not cereal:
        assert hashlib.sha256(source.encode()).hexdigest() == FLEET


def test_bridge_respects_ripe_stock_working_capital_and_three_wheat():
    obs, _ = world()
    slots = [(x, y) for y in range(3) for x in range(3)][:7]
    for x, y in slots:
        crop = game._new_plant("WHEAT", 3, 24)
        crop["yield_units"] = 2
        obs["farms"][0]["tiles"][y][x] = crop
    ns = namespace()
    assert ns["berry_bridge_plan"](obs, 599, {}) == ({}, 0)
    targets, buy = ns["berry_bridge_plan"](obs, 600, {})
    assert len(targets) == buy == 4
    assert len(slots) - len(targets) == 3
    # Seeds bought by this decision are not in the observed shared stock yet.
    assert obs["private"]["seeds"] == {}
    assert ns["berry_bridge_plan"](obs, 200, {"STRAWBERRY": 4}) == (targets, 0)
    target = next(iter(targets))
    obs["farms"][0]["tiles"][target[1]][target[0]] = None
    assert target in ns["berry_bridge_plan"](obs, 200, {"STRAWBERRY": 4})[0]
    obs["farms"][0]["tiles"][target[1]][target[0]] = game._new_plant("STRAWBERRY", 5, 24)
    assert target not in ns["berry_bridge_plan"](obs, 200, {"STRAWBERRY": 3})[0]


def test_bridge_does_not_replace_unripe_cohorts_or_start_after_deadline():
    for day, born in ((5, 4), (6, 3)):
        obs, _ = world(day=day)
        for y in range(2):
            for x in range(4):
                crop = game._new_plant("WHEAT", born, 24)
                obs["farms"][0]["tiles"][y][x] = crop
        assert namespace()["berry_bridge_plan"](obs, 5000, {}) == ({}, 0)


def prefix(source, seat):
    own = get_last_callable(source)
    opponent = get_last_callable(build(berries=0))
    env = make("kaggriculture", configuration={"seed": 5000})
    env.reset()
    actions, days = [], {}
    deaths = escapes = 0
    for _step in range(216):
        views = [env._Environment__get_shared_state(player).observation for player in (0, 1)]
        previous = deepcopy(views[seat]["farms"][seat]["tiles"])
        action = own(views[seat], env.configuration)
        before_farm = views[seat]["farms"][seat]
        positions = deepcopy([before_farm["farmer"], *before_farm["hands"]])
        actions.append(action)
        assert all(work[0] != "BRIDGE" for work in [action["farmer"], *action["hands"]])
        other = opponent(views[1 - seat], env.configuration)
        env.step([action, other] if seat == 0 else [other, action])
        current = env._Environment__get_shared_state(seat).observation
        farm = current["farms"][seat]
        for position, work in zip(positions, [action["farmer"], *action["hands"]], strict=True):
            if work[0] == "PLANT":
                planted = farm["tiles"][position[1]][position[0]]
                assert isinstance(planted, dict) and planted.get("crop") == work[1]
        for y, row in enumerate(farm["tiles"]):
            for x, tile in enumerate(row):
                old = previous[y][x]
                if isinstance(old, dict) and isinstance(tile, dict):
                    deaths += old.get("kind") == "PLANT" and tile.get("kind") == "WEED"
                    escapes += old.get("kind") == "ANIMAL" and tile.get("kind") == "PASTURE"
        if current["hour"] == 0:
            days[current["day"] - 1] = deepcopy(farm)
        assert all(player.status == "ACTIVE" for player in env.state)
    return actions, days, deaths, escapes


@pytest.mark.parametrize("seat", [0, 1])
@pytest.mark.parametrize("cereal", [False, True])
def test_official_bridge_funds_four_day5_berries_and_does_not_displace_day8_cohort(seat, cereal):
    old_actions, old, old_deaths, old_escapes = prefix(build(berries=0, cereal=cereal), seat)
    actions, days, deaths, escapes = prefix(build(cereal=cereal), seat)
    assert actions[:120] == old_actions[:120]
    assert days[4] == old[4]
    planted = [
        tile
        for row in days[5]["tiles"]
        for tile in row
        if isinstance(tile, dict) and tile.get("crop") == "STRAWBERRY"
    ]
    assert len(planted) == 4
    assert all(tile["planted_day"] == 5 and tile["consecutive_unwatered"] == 0 for tile in planted)
    assert (
        sum(
            order[2]
            for action in actions[120:144]
            for order in action["market"]
            if order[:2] == ["BUY_SEED", "STRAWBERRY"]
        )
        == 4
    )
    assert deaths == old_deaths == escapes == old_escapes == 0

    def counts(farm):
        return Counter(
            tile.get("crop", tile.get("animal"))
            for row in farm["tiles"]
            for tile in row
            if isinstance(tile, dict)
        )

    assert counts(days[8])["STRAWBERRY"] >= counts(old[8])["STRAWBERRY"]
    assert counts(days[5])["WHEAT"] >= 3


def test_worker_arrival_releases_unexecuted_plans_but_preserves_real_inputs():
    obs, cfg = world(hands=0)
    farm = obs["farms"][0]
    for x in (2, 3):
        animal = game._new_animal("SHEEP", 0)
        animal.update(consecutive_unfed=1, pending_care_bonus=3)
        farm["tiles"][0][x] = animal
    obs["private"]["shed"] = {"WHEAT": 2}
    ns = namespace(berries=0, arrival_replan=True)
    action = ns["agent"](deepcopy(obs), cfg)
    game._apply_unit_action(farm, obs["private"], 0, action["farmer"], 10, 5, 24, 100)
    # Inputs already picked up belong to the farmer; hired workers arrive empty.
    acquired = dict(obs["private"]["inventories"][0])
    farm["hands"] = [[4, 4], [4, 4], [4, 4]]
    obs["private"]["inventories"].extend([{}, {}, {}])
    obs.update(hour=1, step=121)
    for hour in range(1, 24):
        obs.update(hour=hour, step=120 + hour)
        action = ns["agent"](deepcopy(obs), cfg)
        for worker, work in enumerate([action["farmer"], *action["hands"]]):
            game._apply_unit_action(farm, obs["private"], worker, work, 10, 5, 24, 100)
    assert ns["_DAILY_ROUTES"][0]["workers"] == 4
    assert acquired.get("WHEAT", 0) == 2
    assert all(farm["tiles"][0][x]["fed_today"] for x in (2, 3))
    assert all(farm["tiles"][0][x]["cared_today"] for x in (2, 3))
    remaining = obs["private"]["shed"].get("WHEAT", 0) + sum(
        inv.get("WHEAT", 0) for inv in obs["private"]["inventories"]
    )
    assert remaining == 0


def test_new_workers_share_two_seed_stock_and_finish_plant_day_irrigation():
    obs, cfg = world(day=0, hands=0)
    farm = obs["farms"][0]
    obs["private"]["seeds"] = {"MELON": 2}
    ns = namespace(berries=0, arrival_replan=True)
    for hour in range(12):
        if hour == 1:
            farm["hands"] = [[4, 4], [4, 4]]
            obs["private"]["inventories"].extend([{}, {}])
        obs.update(hour=hour, step=hour)
        action = ns["agent"](deepcopy(obs), cfg)
        requested = Counter(
            work[1] for work in [action["farmer"], *action["hands"]] if work[0] == "PLANT"
        )
        assert all(
            count <= obs["private"]["seeds"].get(crop, 0) for crop, count in requested.items()
        )
        for worker, work in enumerate([action["farmer"], *action["hands"]]):
            game._apply_unit_action(farm, obs["private"], worker, work, 10, 0, 24, 100)
    crops = [
        tile
        for row in farm["tiles"]
        for tile in row
        if isinstance(tile, dict) and tile.get("kind") == "PLANT"
    ]
    assert len(crops) == 2
    assert all(tile["watered_today"] for tile in crops)
    assert obs["private"]["seeds"].get("MELON", 0) == 0


@pytest.mark.parametrize("seat", [0, 1])
def test_clean_loader_and_new_game_reset(seat, tmp_path):
    source = build(cereal=True, arrival_replan=True)
    loaded = get_last_callable(source)
    assert loaded.__name__ == "agent"
    obs, cfg = world(day=0, hands=2)
    obs["farms"][seat] = deepcopy(obs["farms"][0])
    obs["player"] = seat
    obs["private"]["seeds"] = {"MELON": 2}
    expected = loaded(deepcopy(obs), cfg)
    assert loaded(deepcopy(obs), cfg) == expected
    later = deepcopy(obs)
    later.update(day=5, hour=1, step=121)
    loaded(later, cfg)
    assert loaded(deepcopy(obs), cfg) == expected
    artifact = tmp_path / "main.py"
    artifact.write_text(source, encoding="utf-8")
    script = "import json,runpy,sys; n=runpy.run_path(sys.argv[1]); o,c=json.load(sys.stdin); print(json.dumps(n['agent'](o,c)))"
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
