"""Official animal transitions check the finite service DP and deployment guards."""

import gzip
import itertools
import json
import subprocess
import sys
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace

import pytest
from experiments.animal_service import INCUMBENT, animal_dp, build
from kaggle_environments import make
from kaggle_environments.agent import get_last_callable
from kaggle_environments.envs.kaggriculture import kaggriculture as game


def brute_official_value(tile, day, product_prices, feed_prices, manure_prices, work_price=4):
    """Exhaust each legal feed/care/collection schedule through the interpreter."""
    horizon = 30 - day
    animal = tile["animal"]
    product = game.ANIMALS[animal]["product"]
    choices = tuple(itertools.product(((False, False), (True, False), (True, True)), (False, True)))
    best = float("-inf")
    for schedule in itertools.product(choices, repeat=horizon):
        farm = game._new_farm(10, 5000)
        farm["farmer"] = [4, 4]
        farm["tiles"][4][4] = deepcopy(tile)
        private = {"shed": {}, "seeds": {}, "inventories": [{}]}
        value = 0
        for offset, ((feed, care), collect) in enumerate(schedule):
            current_day = day + offset
            current = farm["tiles"][4][4]
            if "animal" not in current:
                break
            if current_day == 29 and (feed or care or collect):
                value = float("-inf")
                break
            fed_before, cared_before = current["fed_today"], current["cared_today"]
            held_before = current["yield_units"]
            inv = private["inventories"][0]
            effort = 0
            if feed and not fed_before:
                inv["WHEAT"] = 1
                game._apply_unit_action(farm, private, 0, ["FEED"], 10, current_day, 24, 100)
                assert inv.get("WHEAT", 0) == 0
                value -= feed_prices[offset]
                effort += 1.25
            if care and not cared_before:
                game._apply_unit_action(farm, private, 0, ["CARE"], 10, current_day, 24, 100)
                effort += 1
            if held_before:
                game._apply_unit_action(farm, private, 0, ["HARVEST"], 10, current_day, 24, 100)
                effort += 1
            did_collect = collect and current["fertilizer_available"]
            if did_collect:
                game._apply_unit_action(
                    farm, private, 0, ["COLLECT_FERTILIZER"], 10, current_day, 24, 100
                )
                effort += 1
            if held_before or did_collect:
                game._apply_unit_action(farm, private, 0, ["DROP"], 10, current_day, 24, 100)
                effort += 1
            value += private["shed"].get(product, 0) * product_prices[offset]
            value += private["shed"].get("FERTILIZER", 0) * manure_prices[offset]
            private["shed"].clear()
            value -= effort * work_price
            if current_day < 29:
                game._daily_refresh_animals(farm, current_day)
        best = max(best, value)
    return best


@pytest.mark.parametrize("animal,born", [("COW", 20), ("SHEEP", 20), ("GOOSE", 24)])
@pytest.mark.parametrize("unfed", [0, 1])
def test_dp_matches_exhaustive_official_three_day_service(animal, born, unfed):
    tile = game._new_animal(animal, born)
    tile.update(
        pending_care_bonus=2, yield_units=2, consecutive_unfed=unfed, fertilizer_available=True
    )
    product, feed, manure = [100, 1, 130], [45, 46, 47], [20, 5, 0]
    result = animal_dp(tile, 27, product, feed, manure)
    assert result["value"] == pytest.approx(brute_official_value(tile, 27, product, feed, manure))


def test_unfed_production_clears_bank_and_current_care_arrives_after_production():
    for fed in (False, True):
        farm = game._new_farm(10, 5000)
        tile = game._new_animal("COW", 16)
        tile.update(pending_care_bonus=2, fed_today=fed, cared_today=True)
        farm["tiles"][4][4] = tile
        game._daily_refresh_animals(farm, 23)
        assert tile["yield_units"] == (3 if fed else 1)
        assert tile["pending_care_bonus"] == int(fed)


def test_low_product_prices_choose_alternating_feed_for_profitable_manure():
    tile = game._new_animal("COW", 0)
    tile.update(fertilizer_available=True)
    result = animal_dp(tile, 24, [1] * 6, [50] * 6, [45] * 6)
    baseline = animal_dp(tile, 24, [1] * 6, [50] * 6, [45] * 6, daily_service=True)
    assert not result["feed"] and not result["care"]
    assert 0 < result["feed_units"] < baseline["feed_units"]
    assert result["value"] > baseline["value"]


def test_saturated_products_and_manure_can_retire_without_day30_value():
    tile = game._new_animal("SHEEP", 0)
    tile.update(fertilizer_available=True)
    result = animal_dp(tile, 24, [1] * 6, [50] * 6, [1] * 6)
    assert result["feed_units"] == result["care_actions"] == 0
    tile = game._new_animal("GOOSE", 25)  # first production is day 29, next is day 30
    tile.update(pending_care_bonus=3, fed_today=True)
    terminal = animal_dp(tile, 29, [200], [1], [100])
    assert terminal["value"] == 0
    assert not terminal["feed"] and not terminal["care"]
    with pytest.raises(ValueError, match="day 29"):
        animal_dp(tile, 29, [200, 200], [1, 1], [100, 100])


def observation(day=24):
    env = make("kaggriculture", configuration={"seed": 5000})
    env.reset()
    obs = deepcopy(env._Environment__get_shared_state(0).observation)
    obs.update(day=day, hour=0, step=24 * day, player=0)
    obs["market"]["prices"].update(WHEAT=50, WOOL=1, MILK=1, EGG=1, FERTILIZER=1)
    for item in ("WOOL", "MILK", "EGG", "FERTILIZER"):
        obs["market"]["inventory"][item] = 12000
    return obs, dict(env.configuration)


def test_deployment_preserves_uncollected_stock_before_deliberate_escape():
    ns = {}
    exec(build(), ns)
    obs, _ = observation()
    tile = game._new_animal("SHEEP", 0)
    tile.update(consecutive_unfed=1, yield_units=3)
    obs["farms"][0]["tiles"][4][4] = tile
    service = ns["animal_service_decisions"](obs, [(4, 4, tile)])[(4, 4)]
    assert service["feed"]  # a hypothetical DP harvest cannot authorize this loss
    tile["yield_units"] = 0
    obs["step"] += 1
    service = ns["animal_service_decisions"](obs, [(4, 4, tile)])[(4, 4)]
    assert not service["feed"] and not service["care"]


def test_early_observation_actions_match_immutable_incumbent():
    root = Path(__file__).resolve().parents[1]
    baseline = gzip.decompress(
        (root / "reports/sources" / f"{INCUMBENT}.py.gz").read_bytes()
    ).decode()
    obs, cfg = observation(day=8)
    tile = game._new_animal("COW", 0)
    obs["farms"][0]["tiles"][4][4] = tile
    assert get_last_callable(build())(deepcopy(obs), cfg) == get_last_callable(baseline)(
        deepcopy(obs), cfg
    )


@pytest.mark.parametrize("player", [0, 1])
def test_official_entrypoint_clean_process_and_daily_reset(tmp_path, player):
    source = build()
    loaded = get_last_callable(source)
    assert loaded.__name__ == "agent"
    obs, cfg = observation()
    obs["player"] = player
    tile = game._new_animal("SHEEP", 0)
    obs["farms"][player]["tiles"][4][4] = tile
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
    obs.update(day=25, step=600)
    assert loaded(deepcopy(obs), cfg) == get_last_callable(source)(deepcopy(obs), cfg)


def test_expired_search_budget_is_visible_and_preserves_incumbent_services(capsys):
    tile = game._new_animal("SHEEP", 0)
    with pytest.raises(TimeoutError, match="budget"):
        animal_dp(tile, 16, [200] * 14, [50] * 14, [30] * 14, deadline=0)
    ns = {}
    exec(build(), ns)
    ticks = iter((0, 1))
    ns["time"] = SimpleNamespace(perf_counter=lambda: next(ticks))
    obs, _ = observation()
    obs["farms"][0]["tiles"][4][4] = tile
    decisions = ns["animal_service_decisions"](obs, [(4, 4, tile)])
    assert decisions[(4, 4)]["feed"] and decisions[(4, 4)]["care"]
    assert "animal_service_budget_fallback" in capsys.readouterr().err
