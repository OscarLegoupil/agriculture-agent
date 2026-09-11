"""Official multi-day wheat cycles and resource failure witnesses."""

import json
import subprocess
import sys
from collections import Counter
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace

import pytest
from experiments.cereal_service import (
    FLEET,
    build,
    cereal_fertilizer_worthwhile,
    cereal_input_orders,
)
from experiments.daily_routes import build as build_fleet
from kaggle_environments import make
from kaggle_environments.agent import get_last_callable
from kaggle_environments.envs.kaggriculture import kaggriculture as game
from kaggle_environments.utils import structify


def field(*, day=8, planted=8, workers=1, seeds=0, fertilizer=0, money=100, tomato_base=60):
    env = make(
        "kaggriculture",
        configuration={
            "seed": 5000,
            "weedSpawnChance": 0,
            "marketParams": {
                "WHEAT": {"base": 50},
                "FERTILIZER": {"base": 10},
                "TOMATO": {"base": tomato_base},
            },
        },
    )
    env.reset(2)
    obs = env.state[0].observation
    obs.update(day=day, hour=0, step=day * 24)
    farm = obs.farms[0]
    farm.update(
        money=money,
        farmer=[4, 4],
        hands=[[3, 4], [2, 4]][: workers - 1],
        tiles=[["LOCKED"] * 10 for _ in range(10)],
    )
    for x in (4, 3, 2)[:workers]:
        farm["tiles"][4][x] = game._new_plant("WHEAT", planted, 24)
    obs.private.update(
        shed={"FERTILIZER": fertilizer} if fertilizer else {},
        seeds={"WHEAT": seeds},
        inventories=[{} for _ in range(workers)],
    )
    env.state = structify(env.state)
    return env


def policy(**kwargs):
    namespace = {}
    exec(build(**kwargs), namespace)
    # Isolate service of existing sites from admission of unrelated new crops.
    namespace["PARAMS"]["crop_tiles"] = 0
    return namespace


def advance(env, action):
    before_step = env.state[0].observation["step"]
    env.state[0].action, env.state[1].action = action, {}
    game.interpreter(env.state, env)
    env.state[0].observation["step"] = before_step + 1
    env.state = structify(env.state)


def act(env, namespace):
    observation = deepcopy(env._Environment__get_shared_state(0).observation)
    return namespace["agent"](observation, env.configuration)


def test_official_four_day_cycle_buys_inputs_produces_five_and_renews_same_site(monkeypatch):
    env, ns = field(), policy()
    actions, orders = [], Counter()
    expenses = Counter()
    original = game._commit_unit

    def commit(operation, item, price, *args):
        success = original(operation, item, price, *args)
        if success and operation in ("BUY_SEED", "BUY_PRODUCT"):
            expenses[operation, item] += price
        return success

    monkeypatch.setattr(game, "_commit_unit", commit)
    for _ in range(96):
        day, hour = env.state[0].observation.day, env.state[0].observation.hour
        action = act(env, ns)
        actions.append((day, hour, action["farmer"]))
        for order in action["market"]:
            if len(order) == 3:
                orders[tuple(order[:2])] += order[2]
        advance(env, action)
    farm, private = env.state[0].observation.farms[0], env.state[0].observation.private
    assert [a for day, _, a in actions if day == 10 and a[0] != "PASS"] == [
        ["PICKUP", "FERTILIZER", 1],
        ["FERTILIZE"],
        ["WATER"],
    ]
    assert [a for day, _, a in actions if day == 11 and a[0] != "PASS"][:4] == [
        ["WATER"],
        ["HARVEST"],
        ["PLANT", "WHEAT"],
        ["WATER"],
    ]
    tile = farm.tiles[4][4]
    assert tile["crop"] == "WHEAT" and tile["planted_day"] == 11
    assert tile["consecutive_unwatered"] == 0
    # One seed is consumed by renewal; the other is the observed next-cycle buffer.
    assert orders["BUY_SEED", "WHEAT"] == 2 and private.seeds["WHEAT"] == 1
    assert orders["BUY_PRODUCT", "FERTILIZER"] == 1
    assert expenses == {("BUY_SEED", "WHEAT"): 20, ("BUY_PRODUCT", "FERTILIZER"): 10}
    assert private.shed.get("WHEAT", 0) + orders["SELL", "WHEAT"] == 5
    assert sum(a == ["FERTILIZE"] for _, _, a in actions) == 1


def test_fertilizer_duration_and_annual_growth_are_official_not_an_average_roi_formula():
    farm, private = game._new_farm(10, 100), game._new_private()
    plant = game._new_plant("WHEAT", 8, 24)
    farm["tiles"][4][4] = plant
    private["inventories"][0]["FERTILIZER"] = 1
    game._apply_unit_action(farm, private, 0, ["FERTILIZE"], 10, 10, 24, 100)
    assert plant["fertilized_until_day"] == 12
    game._apply_unit_action(farm, private, 0, ["WATER"], 10, 10, 24, 100)
    assert plant["yield_units"] == 3
    game._daily_refresh_plants(farm, 10, 24)
    game._apply_unit_action(farm, private, 0, ["WATER"], 10, 11, 24, 100)
    game._apply_unit_action(farm, private, 0, ["HARVEST"], 10, 11, 24, 100)
    assert private["inventories"][0]["WHEAT"] == 5
    assert farm["tiles"][4][4] is None
    unfertilized = game._new_plant("WHEAT", 8, 24)
    farm["tiles"][4][4] = unfertilized
    before = private["inventories"][0]["WHEAT"]
    for day in range(8, 13):
        if day != 9:
            game._apply_unit_action(farm, private, 0, ["WATER"], 10, day, 24, 100)
        if day == 11:
            assert unfertilized["yield_units"] == 3
        if day < 12:
            game._daily_refresh_plants(farm, day, 24)
    game._apply_unit_action(farm, private, 0, ["HARVEST"], 10, 12, 24, 100)
    assert private["inventories"][0]["WHEAT"] - before == 4


def test_missing_fertilizer_does_not_block_required_watering():
    env, ns = field(day=10, planted=8, money=0), policy(renewal=False)
    action = act(env, ns)
    assert action["farmer"] == ["WATER"]
    advance(env, action)
    tile = env.state[0].observation.farms[0].tiles[4][4]
    assert tile["watered_today"] and tile["yield_units"] == 2


def test_two_fertilizer_claims_cannot_spend_the_same_unit():
    env, ns = field(day=10, planted=8, workers=2, fertilizer=1, money=0), policy(renewal=False)
    operations, sold = Counter(), 0
    for _ in range(10):
        action = act(env, ns)
        operations.update(a[0] for a in [action["farmer"], *action["hands"]])
        sold += sum(order[2] for order in action["market"] if order[:2] == ["SELL", "WHEAT"])
        advance(env, action)
    farm = env.state[0].observation.farms[0]
    private = env.state[0].observation.private
    held = sum((farm.tiles[4][x] or {}).get("yield_units", 0) for x in (3, 4))
    delivered = private.shed.get("WHEAT", 0) + sum(
        inv.get("WHEAT", 0) for inv in private.inventories
    )
    assert operations["FERTILIZE"] == 1 and operations["WATER"] == 2
    assert held + delivered + sold == 5


def test_renewal_reserves_real_shared_seeds_and_retains_unfunded_harvest():
    env, ns = field(day=12, planted=8, workers=3, seeds=2, money=0), policy(fertilizer=False)
    for x in (2, 3, 4):
        env.state[0].observation.farms[0].tiles[4][x].update(yield_units=4, watered_today=True)
    sold = 0
    for _ in range(4):
        action = act(env, ns)
        actual = env.state[0].observation.private.seeds.get("WHEAT", 0)
        assert sum(a == ["PLANT", "WHEAT"] for a in [action["farmer"], *action["hands"]]) <= actual
        sold += sum(order[2] for order in action["market"] if order[:2] == ["SELL", "WHEAT"])
        advance(env, action)
    farm, private = env.state[0].observation.farms[0], env.state[0].observation.private
    living = [farm.tiles[4][x] for x in (2, 3, 4) if farm.tiles[4][x] is not None]
    assert len(living) == 2
    assert all(t["planted_day"] == 12 and t["watered_today"] for t in living)
    assert (
        sum(inv.get("WHEAT", 0) for inv in private.inventories)
        + private.shed.get("WHEAT", 0)
        + sold
        == 12
    )


@pytest.mark.parametrize("failed", ["HARVEST", "PLANT", "FERTILIZE"])
def test_failed_operation_cannot_acknowledge_later_prerequisites(failed):
    fertilizing = failed == "FERTILIZE"
    env = field(day=10 if fertilizing else 12, planted=8, seeds=1, fertilizer=1, money=0)
    if not fertilizing:
        env.state[0].observation.farms[0].tiles[4][4].update(yield_units=4, watered_today=True)
    ns = policy()
    injected = False
    for _ in range(12):
        action = act(env, ns)
        if not injected and action["farmer"][0] == failed:
            action["farmer"] = ["PASS"]
            injected = True
        advance(env, action)
    assert injected
    tile = env.state[0].observation.farms[0].tiles[4][4]
    assert tile and tile["crop"] == "WHEAT" and tile["watered_today"]
    if fertilizing:
        assert tile["fertilized_until_day"] == 12 and tile["yield_units"] == 3
    else:
        assert tile["planted_day"] == 12


def test_inputs_respect_prior_spending_order_slots_and_opportunity_cost():
    env = field(day=9, planted=8, money=59)
    obs = deepcopy(env._Environment__get_shared_state(0).observation)
    assert cereal_input_orders(obs, env.configuration, [], True, True) == []
    obs["farms"][0]["money"] = 61
    assert cereal_input_orders(obs, env.configuration, [["HIRE"]], False, True) == [
        ["HIRE"],
        ["BUY_SEED", "WHEAT", 1],
    ]
    orders = [["SELL", "WHEAT", 1]] * 10
    assert cereal_input_orders(obs, env.configuration, orders, True, True) == orders
    tile = obs["farms"][0]["tiles"][4][4]
    obs["market"]["prices"].update(WHEAT=30, FERTILIZER=26)
    assert not cereal_fertilizer_worthwhile(obs, tile)


def test_endgame_admission_requires_a_real_harvest_window():
    for day, planted, expected in [(28, 26, True), (29, 27, False)]:
        env = field(day=day, planted=planted)
        obs = deepcopy(env._Environment__get_shared_state(0).observation)
        assert cereal_fertilizer_worthwhile(obs, obs["farms"][0]["tiles"][4][4]) == expected
        assert not any(
            o[:2] == ["BUY_SEED", "WHEAT"]
            for o in cereal_input_orders(obs, env.configuration, [], True, True)
        )


@pytest.mark.parametrize("day, preferred", [(16, "TOMATO"), (24, "WHEAT")])
def test_renewal_preserves_feasible_parent_crop_choice_and_its_terminal_window(day, preferred):
    env = field(day=day, planted=day - 4, seeds=1, money=0, tomato_base=1000)
    env.state[0].observation.farms[0].tiles[4][4].update(yield_units=4, watered_today=True)
    env.state[0].observation.private.seeds["TOMATO"] = 1
    ns = policy(fertilizer=False, cereal_capacity=True)
    observation = deepcopy(env._Environment__get_shared_state(0).observation)
    forecast, _ = ns["forecast_inventory"](observation, ns["CROPS"], ns["ANIMALS"], ns["SHOPS"])
    crop, values = ns["cereal_preferred_crop"](observation, ns["PARAMS"], forecast, {})
    # Both states have profitable wheat and an actual tomato seed. Only the
    # earlier state offers time for the much higher-value tomato to produce.
    assert values["WHEAT"] > 0 and crop == preferred
    if day == 16:
        assert values["TOMATO"] > 10 * values["WHEAT"]
        context = (ns["PARAMS"], {"WHEAT": 1}, 0, {"WHEAT": 1}, ns["cereal_preferred_crop"])
        # The parent cannot commission an unowned tomato seed at or below its
        # working-capital threshold, even if a later grain sale could finance it.
        assert ns["cereal_renewal_value"](observation, forecast, context) > 0
        context = (*context[:2], 250, *context[3:])
        assert ns["cereal_renewal_value"](observation, forecast, context) > 0
        context = (*context[:2], 251, *context[3:])
        assert ns["cereal_renewal_value"](observation, forecast, context) == 0
    else:
        assert values["TOMATO"] == -float("inf")
    actions = []
    for _ in range(5):
        action = act(env, ns)
        actions.append(action["farmer"])
        advance(env, action)
        tile = env.state[0].observation.farms[0].tiles[4][4]
        if tile and tile["planted_day"] == day and tile["watered_today"]:
            break
    # Yielding the site also releases the old daily route. The parent may
    # deliver the collected grain before commissioning its preferred crop.
    assert [a for a in actions if a != ["DROP"]] == [
        ["HARVEST"],
        ["PLANT", preferred],
        ["WATER"],
    ]
    tile = env.state[0].observation.farms[0].tiles[4][4]
    assert tile["crop"] == preferred and tile["planted_day"] == day and tile["watered_today"]
    assert env.state[0].observation.private.seeds["WHEAT"] == int(preferred != "WHEAT")


def test_build_ablations_official_entrypoint_and_clean_process(tmp_path):
    assert build(fertilizer=False, renewal=False).encode() == build_fleet().encode()
    assert build(fertilizer=False, renewal=False, cereal_capacity=True) == build_fleet(cereal=True)
    for fertilizer, renewal in [(True, True), (True, False), (False, True)]:
        source = build(fertilizer=fertilizer, renewal=renewal)
        assert get_last_callable(source).__name__ == "agent"
    source = build()
    path = tmp_path / "main.py"
    path.write_text(source, encoding="utf-8")
    env = field(day=10, planted=8, fertilizer=1, money=0)
    obs = deepcopy(env._Environment__get_shared_state(0).observation)
    expected = get_last_callable(source)(deepcopy(obs), env.configuration)
    code = "import json,runpy,sys; ns=runpy.run_path(sys.argv[1]); o,c=json.load(sys.stdin); print(json.dumps(ns['agent'](o,c)))"
    result = subprocess.run(
        [sys.executable, "-I", "-c", code, str(path)],
        input=json.dumps([obs, dict(env.configuration)]),
        text=True,
        capture_output=True,
        check=True,
        cwd=tmp_path,
    )
    assert not result.stderr and json.loads(result.stdout) == expected


@pytest.mark.parametrize("seat", [0, 1])
def test_observation_purity_reset_and_new_wheat_identity_in_both_seats(seat):
    env, ns = field(day=12, planted=8, seeds=1, money=0), policy(fertilizer=False)
    obs = deepcopy(env._Environment__get_shared_state(0).observation)
    if seat:
        obs["farms"][0], obs["farms"][1] = obs["farms"][1], obs["farms"][0]
    obs["player"] = seat
    tile = obs["farms"][seat]["tiles"][4][4]
    tile.update(yield_units=4, watered_today=True)
    actions = []
    for _ in range(3):
        before = deepcopy(obs)
        action = ns["agent"](obs, env.configuration)
        assert obs == before
        actions.append(action["farmer"])
        game._apply_unit_action(
            obs["farms"][seat], obs["private"], 0, action["farmer"], 10, 12, 24, 100
        )
        obs["step"] += 1
        obs["hour"] += 1
    assert actions == [["HARVEST"], ["PLANT", "WHEAT"], ["WATER"]]
    assert obs["farms"][seat]["tiles"][4][4]["watered_today"]
    obs.update(day=0, hour=0, step=0)
    fresh = policy(fertilizer=False)
    # Both calls start an episode; there can be no retained renewal operation.
    assert ns["agent"](deepcopy(obs), env.configuration) == fresh["agent"](
        deepcopy(obs), env.configuration
    )


REPLAY = Path(f"reports/replays/breakthrough/{FLEET}-reference-cok-main-5000-0.json")


@pytest.mark.skipif(not REPLAY.exists(), reason="Local replay not distributed in CI")
@pytest.mark.parametrize("cereal_capacity", [False, True])
def test_sequential_opening_parity_and_duplicate_observations(cereal_capacity):
    replay = json.loads(REPLAY.read_bytes())
    candidate_ns, base_ns = {}, {}
    exec(build(cereal_capacity=cereal_capacity), candidate_ns)
    exec(build_fleet(cereal=cereal_capacity), base_ns)
    # Check policy semantics independently of CPU-contention fallbacks. Both
    # retain the exact deterministic 512-insertion cap and episode memories.
    for namespace in (candidate_ns, base_ns):
        namespace["time"] = SimpleNamespace(perf_counter=lambda: 0)
    candidate, base = candidate_ns["agent"], base_ns["agent"]
    for step in replay["steps"][:192]:
        obs = deepcopy(step[0]["observation"])
        expected = base(deepcopy(obs), replay["configuration"])
        actual = candidate(deepcopy(obs), replay["configuration"])
        assert actual == expected
        assert candidate(deepcopy(obs), replay["configuration"]) == actual
