"""Official transition witnesses for marginal herd economics and deployment."""

import copy
import gzip
import json
from collections import Counter
from pathlib import Path

import pytest
from experiments.marginal_herd import (
    INCUMBENT,
    animal_cash_calendar,
    build,
    herd_market_flow,
    herd_projection_inputs,
    marginal_herd_purchase,
    marginal_herd_values,
    project_herd_cash,
)
from kaggle_environments import make
from kaggle_environments.agent import get_last_callable
from kaggle_environments.envs.kaggriculture import kaggriculture as game

from kaggriculture.agent.competitive import ANIMALS, default_price_parameters, inventory_quote


@pytest.mark.parametrize("species", ANIMALS)
@pytest.mark.parametrize("age", [0, 5, 9])
def test_care_bank_and_existing_held_product_follow_official_refresh(species, age):
    farm, private = game._new_farm(10, 10000), game._new_private()
    farm["tiles"][4][4] = game._new_animal(species, 8)
    private["inventories"][0]["WHEAT"] = 100
    product = ANIMALS[species][4]
    # Build the checkpoint with actual service and refresh. Deliberately leave
    # its final harvest held so the forecast must preserve observed inventory.
    for day in range(8, 8 + age):
        for action in (["HARVEST"], ["FEED"], ["CARE"]):
            game._apply_unit_action(farm, private, 0, action, 10, day, 24, 100)
        game._daily_refresh_animals(farm, day)
    day = 8 + age
    tile = farm["tiles"][4][4]
    if age % 2:
        for action in (["FEED"], ["CARE"]):
            game._apply_unit_action(farm, private, 0, action, 10, day, 24, 100)
    expected = animal_cash_calendar(copy.deepcopy(tile), day)
    observed = Counter()
    for work_day in range(day, 30):
        before = private["inventories"][0].get(product, 0)
        game._apply_unit_action(farm, private, 0, ["HARVEST"], 10, work_day, 24, 100)
        gained = private["inventories"][0].get(product, 0) - before
        if gained:
            observed[min(29, work_day + 1)] += gained
        if work_day < 29:
            for action in (["FEED"], ["CARE"]):
                game._apply_unit_action(farm, private, 0, action, 10, work_day, 24, 100)
            game._daily_refresh_animals(farm, work_day)
    assert expected["receipts"] == dict(observed)


@pytest.mark.parametrize(
    ("item", "inventory", "own", "rival"),
    [
        ("WOOL", 10020, 11, 8),
        ("WHEAT", 10040, -7, 13),
        ("FERTILIZER", 10080, -5, -3),
        ("WOOL", 11000, 17, 13),
    ],
)
def test_simultaneous_unit_quotes_and_price_one_supply_match_interpreter(
    item, inventory, own, rival
):
    environment = make("kaggriculture", configuration={"seed": 5000})
    environment.reset(2)
    market = environment.state[0].observation.market
    market.inventory[item] = inventory
    for seat, quantity in enumerate((own, rival)):
        environment.state[0].observation.farms[seat].money = 100000
        environment.state[seat].observation.private.shed = {item: max(0, quantity)}
        environment.state[seat].action = {
            "market": [["SELL" if quantity > 0 else "BUY_PRODUCT", item, abs(quantity)]]
        }
    forecast_inventory, forecast_cash = herd_market_flow(
        inventory, default_price_parameters()[item], own, rival, inventory_quote
    )
    game._process_market(environment.state, environment)
    assert market.inventory[item] == forecast_inventory
    assert environment.state[0].observation.farms[0]["money"] - 100000 == forecast_cash
    if inventory == 11000:
        assert forecast_inventory == inventory
        assert forecast_cash == own


def test_extra_wool_cannibalizes_existing_later_sales():
    environment = make("kaggriculture", configuration={"seed": 5000})
    environment.reset(2)
    spec = default_price_parameters()["WOOL"]
    inventory = spec["I0"]
    unchanged_inventory, existing_receipts = herd_market_flow(
        inventory, spec, 60, 0, inventory_quote
    )
    added_inventory, new_receipts = herd_market_flow(inventory, spec, 40, 0, inventory_quote)
    _, diluted_receipts = herd_market_flow(added_inventory, spec, 60, 0, inventory_quote)
    assert unchanged_inventory > inventory
    assert diluted_receipts < existing_receipts
    assert new_receipts + diluted_receipts - existing_receipts < new_receipts


def test_paid_cohorts_and_feed_are_counted_once_and_unchanged_flows_cancel():
    environment = make("kaggriculture", configuration={"seed": 5000})
    environment.reset(2)
    obs = environment.state[0].observation
    obs.update(day=12, hour=0, step=288)
    obs.private.shed = {"SHEEP": 1, "WOOL": 5}
    obs.private.inventories[0] = {"COW": 1, "WHEAT": 3}
    baseline = herd_projection_inputs(obs)
    addition = herd_projection_inputs(obs, "GOOSE")
    assert baseline[1][0][13] == 2  # Paid sheep and carried cow commission together.
    assert addition[1][0][14] == 3
    calf = game._new_animal("COW", 13)
    lamb = game._new_animal("SHEEP", 13)
    assert sum(flow["WOOL"] for flow in baseline[0][0]) == (
        5 + sum(animal_cash_calendar(lamb, 12)["receipts"].values())
    )
    assert sum(flow["MILK"] for flow in baseline[0][0]) == sum(
        animal_cash_calendar(calf, 12)["receipts"].values()
    )
    assert sum(flow["WHEAT"] for flow in baseline[0][0]) == 3 - 2 * (29 - 13)

    def quote(inventory, spec):
        return 10  # Isolate input accounting from price impact.

    affected = ("EGG", "WHEAT", "FERTILIZER")
    base = project_herd_cash(obs, baseline, 1.0, quote)
    after = project_herd_cash(obs, addition, 1.0, quote)
    limited = project_herd_cash(obs, addition, 1.0, quote, items=affected)
    delta = after["cash"] - base["cash"]
    assert delta == pytest.approx(
        limited["cash"] - sum(base["product_cash"][item] for item in affected)
    )
    calendar = addition[2]
    projected_manure = sum(
        addition[0][0][day]["FERTILIZER"] - baseline[0][0][day]["FERTILIZER"]
        for day in range(12, 30)
    )
    assert delta == pytest.approx(
        10 * (sum(calendar["receipts"].values()) + projected_manure - len(calendar["feed_days"]))
    )


def test_model_is_observation_pure_and_budget_fallback_is_visible(capsys):
    environment = make("kaggriculture", configuration={"seed": 5000})
    environment.reset(2)
    obs = environment.state[0].observation
    obs.update(day=12, hour=0, step=288)
    before = copy.deepcopy(obs)
    values = marginal_herd_values(obs, environment.configuration)
    assert values
    assert obs == before
    assert marginal_herd_purchase(obs, fallback="SHEEP", budget_seconds=0) == "SHEEP"
    assert "marginal_herd_budget_fallback" in capsys.readouterr().err


@pytest.mark.parametrize(
    "base", [INCUMBENT, "fca083cdb5ac82dc4ad39a4227ef60ca57c948f819b565804aa706994f8e61ba"]
)
def test_official_loader_selects_new_admission_and_independent_instances_reset(base):
    first, second = get_last_callable(build(base=base)), get_last_callable(build(base=base))
    assert first.__name__ == "agent"
    assert "marginal_herd_purchase" in first.__code__.co_names
    environment = make("kaggriculture", configuration={"seed": 5000})
    environment.reset(2)
    obs = environment.state[0].observation
    before = first(obs, environment.configuration)
    obs.update(day=12, hour=0, step=288)
    first(obs, environment.configuration)
    obs.update(day=0, hour=0, step=0)
    assert first(obs, environment.configuration) == second(obs, environment.configuration) == before


REPLAY = Path(f"reports/replays/breakthrough/{INCUMBENT}-reference-mooman-main-5000-0.json")


@pytest.mark.skipif(not REPLAY.exists(), reason="Local replay is not distributed with CI")
def test_recorded_startup_actions_match_incumbent_in_both_seats():
    replay = json.loads(REPLAY.read_bytes())
    candidate = get_last_callable(build())
    champion = get_last_callable(
        gzip.decompress(Path(f"reports/sources/{INCUMBENT}.py.gz").read_bytes()).decode()
    )
    for step in replay["steps"][:192]:
        for seat in (0, 1):
            observation = {**step[0]["observation"], **step[seat]["observation"], "player": seat}
            assert candidate(observation, replay["configuration"]) == champion(
                observation, replay["configuration"]
            )


@pytest.mark.skipif(not REPLAY.exists(), reason="Local replay is not distributed with CI")
def test_fleet_admission_preserves_recorded_pre_admission_decisions():
    replay = json.loads(REPLAY.read_bytes())
    base = "fca083cdb5ac82dc4ad39a4227ef60ca57c948f819b565804aa706994f8e61ba"
    candidate = get_last_callable(build(base=base))
    parent = get_last_callable(
        gzip.decompress(Path(f"reports/sources/{base}.py.gz").read_bytes()).decode()
    )
    for step in replay["steps"][:192]:
        for seat in (0, 1):
            obs = {**step[0]["observation"], **step[seat]["observation"], "player": seat}
            assert candidate(obs, replay["configuration"]) == parent(obs, replay["configuration"])


@pytest.mark.skipif(not REPLAY.exists(), reason="Local replay is not distributed with CI")
def test_recorded_late_wool_cohort_is_rejected_after_cannibalization():
    replay = json.loads(REPLAY.read_bytes())
    obs = replay["steps"][12 * 24][0]["observation"]
    values = marginal_herd_values(obs, replay["configuration"])
    assert values["SHEEP"]["net"] < -1000
    assert values["GOOSE"]["net"] > 0
    assert values["SHEEP"]["scenarios"][0]["product_cash_change"]["WOOL"] < 0
