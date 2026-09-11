"""Official sale and consumption witnesses for floor-aware public forecasts."""

import ast
import copy
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace

import pytest
from experiments.floor_forecast import (
    CONTROL,
    build,
    floor_price_scenarios,
    floor_sale_inventory,
)
from kaggle_environments import make
from kaggle_environments.agent import get_last_callable
from kaggle_environments.envs.kaggriculture import kaggriculture as game
from kaggle_environments.utils import structify

from kaggriculture.agent.competitive import (
    ANIMALS,
    CROPS,
    SHOPS,
    default_price_parameters,
    forecast_inventory,
    inventory_quote,
)


@pytest.fixture
def state():
    env = make("kaggriculture", configuration={"seed": 5000})
    env.reset(2)
    raw = json.loads(json.dumps(env.state))
    raw[0]["observation"]["market"]["params"] = default_price_parameters()
    return raw


@pytest.mark.parametrize("item", ["WOOL", "MILK", "WHEAT", "FERTILIZER", "TOMATO"])
@pytest.mark.parametrize("starting_inventory", [9990, 10050, 11000])
def test_sale_inventory_matches_official_unit_execution(state, item, starting_inventory):
    raw = state[0]["observation"]
    market = raw["market"]
    market["inventory"][item] = starting_inventory
    private = raw["private"]
    private["shed"] = {item: 100}
    expected = floor_sale_inventory(starting_inventory, 100, market["params"][item])
    for _ in range(100):
        price = game.market_price(item, market["inventory"][item], market["params"])
        game._commit_unit("SELL", item, price, raw["farms"][0], private, market)
    assert private["shed"][item] == 0
    assert market["inventory"][item] == expected


def test_fractional_expected_supply_only_advances_while_quote_exceeds_one():
    parameters = default_price_parameters()["WOOL"]
    assert inventory_quote(10058, parameters) > 1
    assert inventory_quote(10059, parameters) == 1
    assert floor_sale_inventory(10058, 0.4, parameters) == 10058.4
    assert floor_sale_inventory(10058, 1.4, parameters) == 10059
    assert floor_sale_inventory(10059, 0.4, parameters) == 10059
    with pytest.raises(ValueError, match="nonnegative"):
        floor_sale_inventory(10059, -1, parameters)


@pytest.mark.parametrize("timing", ["early", "spread", "late"])
def test_floor_recovery_follows_actual_shop_ticks(state, timing):
    raw = state[0]["observation"]
    raw.update(day=28, hour=0, step=672)
    raw["town"]["unlocked_shops"] = ["YARN_STORE"] * 8
    raw["market"]["inventory"]["WOOL"] = 10059
    arrivals = [{item: 0 for item in raw["market"]["inventory"]} for _ in range(30)]
    arrivals[29]["WOOL"] = 120
    predicted = floor_price_scenarios(raw, arrivals, 0, SHOPS, timing=timing)["WOOL"][0]
    actual = structify(copy.deepcopy(state))
    actual[0].observation.private["shed"] = {"WOOL": 120}
    env = SimpleNamespace(configuration=structify({}))

    def sell(amount):
        observation = actual[0].observation
        for _ in range(amount):
            quote = game.market_price(
                "WOOL", observation.market["inventory"]["WOOL"], observation.market["params"]
            )
            game._commit_unit(
                "SELL", "WOOL", quote, observation.farms[0], observation.private, observation.market
            )

    for tick in range(6):
        if timing == "early" and tick == 0:
            sell(120)
        game._town_consume(env, actual, 696 + tick * 4)
        if timing == "spread":
            sell(20)
        elif timing == "late" and tick == 5:
            sell(120)
    market = actual[0].observation.market
    assert predicted == game.market_price("WOOL", market["inventory"]["WOOL"], market["params"])
    if timing == "early":
        assert predicted > 200  # Floor sales did not create phantom supply.
    else:
        assert predicted == 1


@pytest.mark.parametrize("animal_service", [False, True])
def test_standalone_loader_selects_agent_and_forecast_uses_only_public_state(state, animal_service):
    source = build(animal_service=animal_service)
    functions = [node.name for node in ast.parse(source).body if isinstance(node, ast.FunctionDef)]
    assert functions[-1] == "agent"
    namespace = {"__name__": "floor_candidate"}
    exec(compile(source, "floor_candidate", "exec"), namespace)
    observation = state[0]["observation"]
    observation.update(day=28, hour=0, step=672, player=0)
    before = copy.deepcopy(observation)
    first = namespace["forecast_inventory"](observation, CROPS, ANIMALS, SHOPS)
    assert observation == before
    observation["private"] = {"not_available_to_forecast": True}
    assert namespace["forecast_inventory"](observation, CROPS, ANIMALS, SHOPS) == first
    assert set(first[1]) == set(observation["market"]["inventory"])
    assert all(len(values) == 1 for values in first[1].values())
    assert hashlib.sha256(source.encode()).hexdigest() != CONTROL


def test_no_floor_and_no_supply_matches_incumbent(state):
    observation = state[0]["observation"]
    observation.update(day=24, hour=0, step=576)
    observation["town"]["unlocked_shops"] = ["YARN_STORE", "PET_CAFE"] * 4
    namespace = {"__name__": "floor_candidate"}
    exec(build(), namespace)
    assert namespace["forecast_inventory"](
        observation, CROPS, ANIMALS, SHOPS
    ) == forecast_inventory(observation, CROPS, ANIMALS, SHOPS)


REPLAY = Path(
    "reports/replays/breakthrough/"
    "6c613e921625eb2058dc07a0f0ea50f48ba9c5f1f2c730e4c0066f6f528b9a6d-"
    "reference-mooman-main-5003-0.json"
)


@pytest.mark.skipif(not REPLAY.exists(), reason="Local replay is not distributed in CI")
def test_reachable_floor_recovery_changes_profitable_rescue():
    from experiments.fleet_animal_service import fleet_animal_dp

    observation = json.loads(REPLAY.read_bytes())["steps"][504][0]["observation"]
    namespace = {"__name__": "floor_candidate"}
    exec(build(), namespace)
    _, traces = namespace["forecast_inventory"](observation, CROPS, ANIMALS, SHOPS)
    prices = {
        item: [
            observation["market"]["prices"][item],
            *(0.5 * observation["market"]["prices"][item] + 0.5 * value for value in values),
        ]
        for item, values in traces.items()
    }
    tile = observation["farms"][0]["tiles"][3][1]
    assert tile["animal"] == "SHEEP" and tile["consecutive_unfed"] == 1
    decision = fleet_animal_dp(
        tile, 21, prices["WOOL"], prices["WHEAT"], prices["FERTILIZER"], travel_actions=8 / 3
    )
    _, original_traces = forecast_inventory(observation, CROPS, ANIMALS, SHOPS)
    original_prices = {
        item: [
            observation["market"]["prices"][item],
            *(0.5 * observation["market"]["prices"][item] + 0.5 * value for value in values),
        ]
        for item, values in original_traces.items()
    }
    previous = fleet_animal_dp(
        tile,
        21,
        original_prices["WOOL"],
        original_prices["WHEAT"],
        original_prices["FERTILIZER"],
        travel_actions=8 / 3,
    )
    assert not previous["feed"]
    assert decision["feed"] and not decision["care"]


@pytest.mark.parametrize("animal_service", [False, True])
def test_clean_directory_official_entrypoint_and_both_seat_actions(
    state, animal_service, tmp_path, monkeypatch
):
    source = build(animal_service=animal_service)
    executable = tmp_path / "main.py"
    executable.write_text(source, encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    packaged = get_last_callable(executable.read_text(encoding="utf-8"), path=str(executable))
    direct = {}
    exec(source, direct)
    assert packaged.__name__ == "agent"
    for seat in (0, 1):
        observation = copy.deepcopy(
            {**state[0]["observation"], **state[seat]["observation"], "player": seat, "step": 0}
        )
        expected = direct["agent"](copy.deepcopy(observation), {})
        assert packaged(copy.deepcopy(observation), {}) == expected
        assert packaged(copy.deepcopy(observation), {}) == expected
