"""Consequential official-transition contracts for the isolated offline runner."""

import gzip
import json
from copy import deepcopy

import pytest
from kaggle_environments import make
from kaggle_environments.envs.kaggriculture import kaggriculture as game
from scripts.diagnose_fixed_shops import (
    LABEL,
    FixedShopSchedule,
    control_comparison,
    digest,
    run_case,
)


def environment():
    env = make("kaggriculture", configuration={"seed": 5000, "weedSpawnChance": 0.3})
    env.reset(2)
    for seat in (0, 1):
        state = env.state[seat]
        state.action = {}
        state.observation.step = 71
        state.observation.private["inventories"] = [{"WHEAT": 3}]
        farm = env.state[0].observation.farms[seat]
        farm["hands"] = [[0, 0]]
        farm["farmer"] = [0, 1]
        farm.tiles[1][1] = game._new_plant("WHEAT", 0, 24)
        farm.tiles[1][1]["watered_today"] = True
    return env


def test_unchanged_schedule_reproduces_entire_official_transition():
    ordinary, changed = environment(), environment()
    original_function = game._end_of_day
    game.interpreter(ordinary.state, ordinary)
    observed = ordinary.state[0].observation.town.unlocked_shops[0]
    with FixedShopSchedule(changed, [observed] * 8) as patch:
        game.interpreter(changed.state, changed)
    assert game._end_of_day is original_function
    assert changed.state == ordinary.state
    assert patch.events[0]["official_draw"] == observed
    assert not patch.events[0]["changed"]
    assert patch.events[0]["visible_step"] == 72
    assert any(
        isinstance(tile, dict) and tile.get("kind") == "WEED"
        for farm in changed.state[0].observation.farms
        for row in farm.tiles
        for tile in row
    )
    assert changed.state[0].observation.private.inventories == [{}]
    assert changed.state[0].observation.private.shed["WHEAT"] == 3
    assert changed.state[0].observation.farms[0].hands == []


def test_changed_shop_preserves_weeds_and_affects_demand_only_next_turn():
    yarn, pizza = environment(), environment()
    configs = [deepcopy(env.configuration) for env in (yarn, pizza)]
    initial_keys = [set(env.state[0].observation) for env in (yarn, pizza)]
    traces = []
    for env, shop in ((yarn, "YARN_STORE"), (pizza, "PIZZA_SHOP")):
        with FixedShopSchedule(env, [shop] * 8) as patch:
            game.interpreter(env.state, env)
            traces.append(patch.events)
    assert traces[0][0]["official_draw"] == traces[1][0]["official_draw"]
    assert traces[0][0]["post_official_farms_sha256"] == traces[1][0]["post_official_farms_sha256"]
    assert yarn.state[0].observation.farms == pizza.state[0].observation.farms
    assert yarn.state[0].observation.market == pizza.state[0].observation.market
    for index, (env, shop) in enumerate(((yarn, "YARN_STORE"), (pizza, "PIZZA_SHOP"))):
        assert env.configuration == configs[index]
        assert set(env.state[0].observation) == initial_keys[index]
        for seat in (0, 1):
            assert env.state[seat].observation.town.unlocked_shops == [shop]
            env.state[seat].observation.step = 72
        game.interpreter(env.state, env)
    inventory_yarn = yarn.state[0].observation.market.inventory
    inventory_pizza = pizza.state[0].observation.market.inventory
    assert inventory_yarn["WOOL"] == inventory_pizza["WOOL"] - 2
    assert inventory_pizza["TOMATO"] == inventory_yarn["TOMATO"] - 1
    assert inventory_pizza["WHEAT"] == inventory_yarn["WHEAT"] - 1
    assert inventory_pizza["MILK"] == inventory_yarn["MILK"] - 1


def test_no_append_means_no_override_and_exception_restores_interpreter():
    env = environment()
    original = game._end_of_day
    with (
        pytest.raises(RuntimeError, match="sentinel"),
        FixedShopSchedule(env, ["YARN_STORE"] * 8) as patch,
    ):
        game._end_of_day(env.state, env, 0)
        assert env.state[0].observation.town.unlocked_shops == []
        assert patch.events == []
        raise RuntimeError("sentinel")
    assert game._end_of_day is original


@pytest.mark.parametrize("schedule", [[], ["YARN_STORE"] * 7, ["UNKNOWN"] * 8])
def test_incomplete_or_invalid_schedule_is_rejected(schedule):
    with pytest.raises(ValueError, match="donor schedule"):
        FixedShopSchedule(environment(), schedule)


def test_control_requires_matching_actions_and_states(tmp_path):
    recorded = {"steps": [[{"observation": {"money": 3}, "action": {}}]]}
    raw = json.dumps(recorded).encode()
    path = tmp_path / "donor.json"
    path.write_bytes(raw)
    donor = {"replay_path": str(path), "replay_sha256": digest(raw)}
    assert control_comparison(recorded, donor)["observations_match"]
    changed = deepcopy(recorded)
    changed["steps"][0][0]["action"] = {"farmer": ["PASS"]}
    assert control_comparison(changed, donor)["first_action_difference"] == 0
    changed["steps"][0][0]["observation"]["money"] = 4
    assert control_comparison(changed, donor)["first_observation_difference"] == 0
    shortened = control_comparison({"steps": []}, donor)
    assert not shortened["step_count_matches"]
    assert not shortened["observations_match"]


def test_one_turn_runner_keeps_offline_metadata_outside_policy_observations(tmp_path):
    policy = tmp_path / "main.py"
    policy.write_text(
        "def agent(obs, configuration=None):\n"
        "    assert 'donor' not in obs and 'schedule' not in obs\n"
        "    assert 'donor' not in configuration and 'schedule' not in configuration\n"
        "    return {}\n"
    )
    env = make("kaggriculture", configuration={"seed": 5000, "episodeSteps": 2})
    case = {
        **LABEL,
        "case_id": "one-official-turn-contract",
        "candidate_path": str(policy),
        "candidate_sha256": digest(policy.read_bytes()),
        "opponent": str(policy),
        "configuration": dict(env.configuration),
        "seed": 5000,
        "seat": 0,
        "is_donor_policy_control": False,
    }
    schedule = ["YARN_STORE"] * 8
    row = run_case((case, {"schedule": schedule, "schedule_sha256": "test"}, tmp_path))
    assert row["statuses"] == ["DONE", "DONE"]
    assert row["runtime_by_seat"]["0"]["calls"] == 1
    assert row["runtime_by_seat"]["0"]["stderr_turns"] == 0
    assert not row["competitive_score_eligible"]
    assert row["shop_interventions"] == []
    from pathlib import Path

    archive = Path(row["replay_path"]).read_bytes()
    assert digest(archive) == row["replay_archive_sha256"]
    wrapped = json.loads(gzip.decompress(archive))
    assert not wrapped["competitive_score_eligible"]
    assert "steps" not in wrapped
    assert len(wrapped["offline_replay"]["steps"]) == 2
