"""Official rescue, retirement, marginal-value and fleet integration contracts."""

import gzip
import json
import subprocess
import sys
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace

import pytest
from experiments.animal_service import animal_dp
from experiments.fleet_animal_service import CONTROL, build, fleet_animal_dp
from kaggle_environments import make
from kaggle_environments.agent import get_last_callable
from kaggle_environments.envs.kaggriculture import kaggriculture as game
from kaggle_environments.utils import structify


def field(*, rescue=True, workers=1):
    env = make(
        "kaggriculture",
        configuration={
            "seed": 5000,
            "weedSpawnChance": 0,
            "marketParams": {
                "WHEAT": {"base": 100},
                "WOOL": {"base": 40 if rescue else 1},
                "CARROT": {"base": 10},
                "FERTILIZER": {"base": 1},
            },
        },
    )
    env.reset(2)
    observation = env.state[0].observation
    observation.update(day=24, hour=22, step=24 * 24 + 22)
    farm = observation.farms[0]
    farm.update(
        farmer=[4, 4],
        hands=[[4, 3]][: workers - 1],
        money=0,
        tiles=[["LOCKED"] * 10 for _ in range(10)],
    )
    for x, y in [(4, 4), (4, 3)][:workers]:
        tile = game._new_animal("SHEEP", 20)
        tile.update(consecutive_unfed=1, pending_care_bonus=4, fertilizer_available=False)
        farm["tiles"][y][x] = tile
    carrot = game._new_plant("CARROT", 22, 24)
    carrot.update(consecutive_unwatered=0, watered_today=False)
    farm["tiles"][4][3] = carrot
    observation.private.update(shed={}, seeds={}, inventories=[{"WHEAT": 2}, *[{}] * (workers - 1)])
    env.state = structify(env.state)
    return env


def namespace(enabled=True):
    result = {}
    exec(build(enabled=enabled), result)
    return result


def act(env, ns):
    return ns["agent"](
        deepcopy(env._Environment__get_shared_state(0).observation), env.configuration
    )


def advance(env, action):
    step = env.state[0].observation["step"]
    env.state[0].action, env.state[1].action = action, {}
    game.interpreter(env.state, env)
    env.state[0].observation["step"] = step + 1
    env.state = structify(env.state)


def test_marginal_dp_preserves_recurrence_and_does_not_credit_held_products_twice():
    tile = game._new_animal("SHEEP", 20)
    tile.update(consecutive_unfed=1, pending_care_bonus=4)
    prices = ([40] * 6, [100] * 6, [1] * 6)
    result = fleet_animal_dp(tile, 24, *prices)
    assert result["value"] == animal_dp(tile, 24, *prices)["value"] == 18
    assert result["feed"] and result["care"]
    assert result["today_values"] == {(0, 0): 0, (1, 0): -18, (1, 1): 18}
    assert result["service_gain"] == 18 and result["service_credit"] == 27
    tile["yield_units"] = 3
    held = fleet_animal_dp(tile, 24, *prices)
    # A common HARVEST and DROP add revenue and effort to both alternatives.
    assert held["value"] - result["value"] == 3 * 40 - 8
    assert held["service_gain"] == result["service_gain"]
    assert held["service_credit"] == result["service_credit"]


def test_official_banked_first_harvest_rescue_survives_fleet_economic_gate():
    candidate, control = field(), field()
    ns, old = namespace(), namespace(False)
    candidate_action, control_action = act(candidate, ns), act(control, old)
    assert candidate_action["farmer"] == ["FEED"]
    assert control_action["farmer"] == ["WEST"]
    advance(candidate, candidate_action)
    advance(control, control_action)
    assert act(candidate, ns)["farmer"] == ["CARE"]
    advance(candidate, act(candidate, ns))
    advance(control, act(control, old))
    assert "animal" not in control.state[0].observation.farms[0].tiles[4][4]
    tile = candidate.state[0].observation.farms[0].tiles[4][4]
    assert tile["animal"] == "SHEEP" and tile["pending_care_bonus"] == 5
    harvested = 0
    feed_actions = 1
    for _ in range(48):
        action = act(candidate, ns)
        before = candidate.state[0].observation
        tile = before.farms[0].tiles[4][4]
        if action["farmer"] == ["HARVEST"] and before.farms[0].farmer == [4, 4]:
            harvested += tile["yield_units"]
        feed_actions += action["farmer"] == ["FEED"]
        advance(candidate, action)
    # The immediate five-unit bank is real: two feeds obtain six units before
    # retirement. At the initial quotes, 6*40 exceeds the 2*100 feed cost.
    assert harvested == 6 and feed_actions == 2
    assert 6 * 40 - 2 * 100 > 0


def test_negative_wool_service_cannot_be_reintroduced_by_fleet_or_fallback():
    env, ns = field(rescue=False), namespace()
    observation = deepcopy(env._Environment__get_shared_state(0).observation)
    tile = observation["farms"][0]["tiles"][4][4]
    decision = ns["fleet_animal_decisions"](observation, [(4, 4, tile)])[(4, 4)]
    assert not decision["feed"] and not decision["care"]
    for _ in range(2):
        action = act(env, ns)
        assert action["farmer"][0] not in ("FEED", "CARE")
        assert not any(order[:2] == ["BUY_PRODUCT", "WHEAT"] for order in action["market"])
        advance(env, action)
    assert "animal" not in env.state[0].observation.farms[0].tiles[4][4]


def test_failed_feed_retries_before_care_and_does_not_acknowledge_phantom_input():
    env, ns = field(), namespace()
    env.state[0].observation.update(hour=20, step=24 * 24 + 20)
    env.state = structify(env.state)
    assert act(env, ns)["farmer"] == ["FEED"]
    action = act(env, ns)
    action["farmer"] = ["PASS"]
    advance(env, action)
    action = act(env, ns)
    assert action["farmer"] == ["FEED"]
    advance(env, action)
    assert act(env, ns)["farmer"] == ["CARE"]


def test_shared_feed_reservations_allow_only_one_of_two_rescues():
    env, ns = field(workers=2), namespace()
    env.state[0].observation.update(hour=20, step=24 * 24 + 20)
    env.state[0].observation.private.update(shed={"WHEAT": 1}, inventories=[{}, {}])
    env.state = structify(env.state)
    pickups = feeds = 0
    for _ in range(4):
        action = act(env, ns)
        for op in [action["farmer"], *action["hands"]]:
            if op[:2] == ["PICKUP", "WHEAT"]:
                pickups += op[2]
            feeds += op == ["FEED"]
        advance(env, action)
    assert pickups == feeds == 1


@pytest.mark.parametrize("seat", [0, 1])
def test_clean_artifact_observation_purity_episode_reset_and_final_day(tmp_path, seat):
    source = build()
    assert get_last_callable(source).__name__ == "agent"
    env, ns = field(), namespace()
    obs = deepcopy(env._Environment__get_shared_state(0).observation)
    if seat:
        obs["farms"].reverse()
    obs["player"] = seat
    before = deepcopy(obs)
    expected = ns["agent"](obs, env.configuration)
    assert obs == before
    artifact = tmp_path / "main.py"
    artifact.write_text(source, encoding="utf-8")
    script = "import json,runpy,sys; n=runpy.run_path(sys.argv[1]); o,c=json.load(sys.stdin); print(json.dumps(n['agent'](o,c)))"
    result = subprocess.run(
        [sys.executable, "-I", "-c", script, str(artifact)],
        input=json.dumps([obs, dict(env.configuration)]),
        text=True,
        capture_output=True,
        check=True,
        cwd=tmp_path,
    )
    assert not result.stderr and json.loads(result.stdout) == expected
    obs.update(day=0, hour=0, step=0)
    assert ns["agent"](deepcopy(obs), env.configuration) == namespace()["agent"](
        deepcopy(obs), env.configuration
    )
    obs.update(day=29, hour=0, step=696)
    tile = obs["farms"][seat]["tiles"][4][4]
    service = ns["fleet_animal_decisions"](obs, [(4, 4, tile)])[(4, 4)]
    assert not service["feed"] and not service["care"] and service["service_credit"] == 0


def test_expired_dp_budget_is_visible_and_retains_control_path(capsys):
    env, ns = field(), namespace()
    obs = deepcopy(env._Environment__get_shared_state(0).observation)
    tile = obs["farms"][0]["tiles"][4][4]
    ticks = iter((0, 1))
    ns["time"] = SimpleNamespace(perf_counter=lambda: next(ticks))
    assert ns["fleet_animal_decisions"](obs, [(4, 4, tile)]) == {}
    assert "fleet_animal_budget_fallback" in capsys.readouterr().err


def test_interrupted_episode_cannot_reuse_same_day_price_scenarios():
    env, reused, fresh = field(rescue=False), namespace(), namespace()
    observation = deepcopy(env._Environment__get_shared_state(0).observation)
    observation.update(day=16, hour=0, step=384)
    tile = observation["farms"][0]["tiles"][4][4]
    tile.update(placed_day=14, pending_care_bonus=1)
    low = reused["fleet_animal_decisions"](observation, [(4, 4, tile)])[(4, 4)]
    assert not low["feed"]
    assert reused["_FLEET_ANIMAL_SERVICES"][0]["scenarios"]["WOOL"][0] == 1
    opening = deepcopy(observation)
    opening.update(day=0, hour=0, step=0)
    reused["agent"](opening, env.configuration)
    assert 0 not in reused["_FLEET_ANIMAL_SERVICES"]
    observation["market"]["prices"]["WOOL"] = 1000
    observation["market"]["params"]["WOOL"]["base"] = 1000
    expected = fresh["fleet_animal_decisions"](observation, [(4, 4, tile)])[(4, 4)]
    actual = reused["fleet_animal_decisions"](observation, [(4, 4, tile)])[(4, 4)]
    assert expected["feed"] and actual == expected
    assert reused["_FLEET_ANIMAL_SERVICES"][0]["scenarios"]["WOOL"][0] == 1000


REPLAY = Path(f"reports/replays/breakthrough/{CONTROL}-reference-mooman-main-5000-0.json")


@pytest.mark.skipif(not REPLAY.exists(), reason="Local replay not distributed in CI")
def test_sequential_first_sixteen_days_preserve_exact_control_actions():
    assert build(enabled=False).encode() == gzip.decompress(
        Path(f"reports/sources/{CONTROL}.py.gz").read_bytes()
    )
    replay = json.loads(REPLAY.read_bytes())
    candidate, control = namespace(), namespace(False)
    for ns in (candidate, control):
        ns["time"] = SimpleNamespace(perf_counter=lambda: 0)
    for step in replay["steps"][:384]:
        observation = deepcopy(step[0]["observation"])
        expected = control["agent"](deepcopy(observation), replay["configuration"])
        actual = candidate["agent"](deepcopy(observation), replay["configuration"])
        assert actual == expected
        assert candidate["agent"](deepcopy(observation), replay["configuration"]) == actual
