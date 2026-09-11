"""Animal circuits execute their prerequisites through official transitions."""

import gzip
import json
import subprocess
import sys
from copy import deepcopy
from pathlib import Path

import pytest
from experiments.service_routes import INCUMBENT, build
from kaggle_environments import make
from kaggle_environments.agent import get_last_callable
from kaggle_environments.envs.kaggriculture import kaggriculture as game


def observation(*, hour=12, wheat=2, workers=1):
    env = make("kaggriculture", configuration={"seed": 0})
    env.reset()
    obs = deepcopy(env.state[0].observation)
    obs.update(day=5, hour=hour, step=5 * 24 + hour, player=0)
    farm = game._new_farm(10, 5000)
    farm["farmer"] = [4, 4]
    farm["hands"] = [[4, 5] for _ in range(workers - 1)]
    for target in ((4, 1), (3, 1)):
        animal = game._new_animal("SHEEP", 0)
        animal.update(pending_care_bonus=3, fertilizer_available=True)
        farm["tiles"][target[1]][target[0]] = animal
    obs["farms"][0] = farm
    obs["private"] = {
        "shed": {"WHEAT": wheat},
        "seeds": {},
        "inventories": [{} for _ in range(workers)],
    }
    return obs, dict(env.configuration)


def policy(source=None):
    namespace = {}
    exec(build() if source is None else source, namespace)
    return namespace


def simulate(namespace, obs, cfg, until=24):
    history = []
    for hour in range(obs["hour"], until):
        obs.update(hour=hour, step=obs["day"] * 24 + hour)
        action = namespace["agent"](deepcopy(obs), cfg)
        history.append(action)
        farm = obs["farms"][obs["player"]]
        for worker, work in enumerate([action["farmer"], *action["hands"]]):
            game._apply_unit_action(farm, obs["private"], worker, work, 10, obs["day"], 24, 100)
    return history


def test_complete_circuit_acquires_shared_feed_and_finishes_two_cohorts():
    obs, cfg = observation()
    ns = policy()
    history = simulate(ns, obs, cfg)
    farm = obs["farms"][0]
    assert history[0]["farmer"] == ["PICKUP", "WHEAT", 2]
    for x, y in ((4, 1), (3, 1)):
        assert farm["tiles"][y][x]["fed_today"]
        assert farm["tiles"][y][x]["cared_today"]
        assert not farm["tiles"][y][x]["fertilizer_available"]
    game._daily_refresh_animals(farm, 5)
    assert [farm["tiles"][y][x]["yield_units"] for x, y in ((4, 1), (3, 1))] == [4, 4]
    assert obs["private"]["inventories"][0].get("FERTILIZER") == 2


def test_pickup_reservations_prevent_overbooking_multiple_workers():
    obs, cfg = observation(hour=8, wheat=1, workers=4)
    ns = policy()
    action = ns["agent"](obs, cfg)
    pickups = [
        work[2] for work in [action["farmer"], *action["hands"]] if work[:2] == ["PICKUP", "WHEAT"]
    ]
    assert sum(pickups) <= 1
    plans = ns["_SERVICE_STATE"][0]["plans"]
    assert sum(op == "FEED" for plan in plans.values() for _, op, _ in plan["ops"]) <= 1
    # New market purchases are not credited to today's executable routes.
    obs["private"]["shed"]["WHEAT"] = 0
    obs.update(step=obs["step"] + 1, hour=obs["hour"] + 1)
    action = ns["agent"](obs, cfg)
    assert not any(work[0] == "PICKUP" for work in [action["farmer"], *action["hands"]])
    assert ns["_SERVICE_DIAGNOSTICS"]["input_invalidations"] >= 1


def test_commitment_survives_distracting_new_task_and_releases_replaced_animal():
    obs, cfg = observation()
    ns = policy()
    simulate(ns, obs, cfg, until=14)
    plan = ns["_SERVICE_STATE"][0]["plans"][0]
    target = plan["ops"][0][0]
    # Another nearby cow offers fertilizer but cannot steal the committed feed.
    distraction = game._new_animal("COW", 0)
    distraction.update(fed_today=True, cared_today=True, fertilizer_available=True)
    obs["farms"][0]["tiles"][3][3] = distraction
    obs.update(hour=14, step=134)
    chosen = ns["agent"](deepcopy(obs), cfg)
    assert chosen["farmer"] == ns["move"](tuple(obs["farms"][0]["farmer"]), target)
    # A removed animal releases its old operations; no invalid FEED loop.
    obs["farms"][0]["tiles"][target[1]][target[0]] = {"kind": "PASTURE"}
    obs.update(hour=15, step=135)
    ns["agent"](deepcopy(obs), cfg)
    assert all(
        target != location
        for plan in ns["_SERVICE_STATE"][0]["plans"].values()
        for location, _, _ in plan["ops"]
    )


@pytest.mark.parametrize("player", [0, 1])
def test_fresh_and_reused_process_reset_to_same_day_opening(player):
    obs, cfg = observation()
    if player:
        obs["farms"][1] = deepcopy(obs["farms"][0])
        obs["player"] = 1
    ns = policy()
    simulate(ns, deepcopy(obs), cfg, until=15)
    restarted = deepcopy(obs)
    restarted.update(day=6, hour=0, step=144)
    assert ns["agent"](deepcopy(restarted), cfg) == policy()["agent"](deepcopy(restarted), cfg)
    assert ns["agent"](deepcopy(restarted), cfg) == ns["agent"](deepcopy(restarted), cfg)


def test_endgame_abandons_care_that_cannot_reach_a_sale():
    obs, cfg = observation(hour=0)
    obs.update(day=28, step=672)
    ns = policy()
    ns["agent"](obs, cfg)
    assert not any(
        op == "CARE"
        for plan in ns["_SERVICE_STATE"][0]["plans"].values()
        for _, op, _ in plan["ops"]
    )
    obs.update(day=29, step=696)
    ns["agent"](obs, cfg)
    assert ns["_SERVICE_STATE"][0]["plans"] == {}


def test_single_day_counterfactual_reports_actual_service_difference():
    original = gzip.decompress(
        (
            Path(__file__).resolve().parents[1] / "reports/sources" / f"{INCUMBENT}.py.gz"
        ).read_bytes()
    ).decode()
    obs, cfg = observation(hour=12)
    baseline, candidate = deepcopy(obs), deepcopy(obs)
    simulate(policy(original), baseline, cfg)
    simulate(policy(), candidate, cfg)

    # Both receive identical fixed current assets and inventory. No market or
    # opponent is frozen in a claimed full-season result: this is a day probe.
    def completed(state):
        tiles = (state["farms"][0]["tiles"][y][x] for x, y in ((4, 1), (3, 1)))
        return sum(
            tile["fed_today"] + tile["cared_today"] + (not tile["fertilizer_available"])
            for tile in tiles
        )

    assert completed(candidate) == 6
    assert completed(baseline) == 2
    for state in (baseline, candidate):
        game._daily_refresh_animals(state["farms"][0], 5)
    assert sum(candidate["farms"][0]["tiles"][1][x]["yield_units"] for x in (3, 4)) == 8
    assert sum(baseline["farms"][0]["tiles"][1][x]["yield_units"] for x in (3, 4)) == 2


def test_official_entrypoint_and_clean_directory_source_parity(tmp_path):
    source = build()
    assert get_last_callable(source).__name__ == "agent"
    artifact = tmp_path / "main.py"
    artifact.write_text(source, encoding="utf-8")
    obs, cfg = observation()
    expected = policy(source)["agent"](deepcopy(obs), cfg)
    runner = (
        "import json,runpy,sys; namespace=runpy.run_path(sys.argv[1]); "
        "obs,cfg=json.load(sys.stdin); print(json.dumps(namespace['agent'](obs,cfg)))"
    )
    completed = subprocess.run(
        [sys.executable, "-I", "-c", runner, str(artifact)],
        input=json.dumps([obs, cfg]),
        text=True,
        capture_output=True,
        cwd=tmp_path,
        check=True,
    )
    assert not completed.stderr
    assert json.loads(completed.stdout) == expected
