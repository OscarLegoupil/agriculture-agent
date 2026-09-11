"""Official care-bank contracts and standalone forecast composition."""

import gzip
import hashlib
import json
import subprocess
import sys
from copy import deepcopy
from pathlib import Path

import pytest
from experiments.care_bank_forecast import CONTROL, FLOOR_CONTROL, animal_supply, build
from kaggle_environments import make
from kaggle_environments.agent import get_last_callable
from kaggle_environments.envs.kaggriculture import kaggriculture as game

from kaggriculture.agent.competitive import ANIMALS


@pytest.mark.parametrize("animal", ["COW", "SHEEP", "GOOSE"])
@pytest.mark.parametrize("day,placed,bank,held", [(3, 0, 3, 0), (16, 2, 1, 2), (28, 25, 2, 1)])
def test_perfect_future_care_matches_official_refresh(animal, day, placed, bank, held):
    tile = game._new_animal(animal, placed)
    tile.update(pending_care_bonus=bank, yield_units=held)
    expected = dict(animal_supply(tile, day, ANIMALS, care_rate=1.0))
    original = deepcopy(tile)
    # Existing product is collected separately from modeled new production.
    tile["yield_units"] = 0
    farm = dict(tiles=[[tile]])
    actual = {}
    for current in range(day, 29):
        tile.update(fed_today=True, cared_today=True)
        game._daily_refresh_animals(farm, current)
        if tile["yield_units"]:
            actual[current + 1] = tile["yield_units"]
            tile["yield_units"] = 0
    assert actual == expected
    assert dict(animal_supply(original, day, ANIMALS, care_rate=1.0)) == expected
    assert all(future <= 29 for future in expected)


def test_startup_bank_and_known_today_care_preserve_production_order():
    cow = game._new_animal("COW", 0)
    cow.update(pending_care_bonus=3, cared_today=False)
    assert dict(animal_supply(cow, 3, ANIMALS))[8] == 6
    cow.update(pending_care_bonus=0, cared_today=True)
    forecast = dict(animal_supply(cow, 7, ANIMALS))
    assert forecast[8] == 1  # Today's care cannot increase tonight's production.
    assert forecast[10] == pytest.approx(2.8)
    cow["cared_today"] = False
    assert dict(animal_supply(cow, 7, ANIMALS))[10] == pytest.approx(2.6)
    assert animal_supply(cow, 29, ANIMALS) == ()


@pytest.mark.parametrize("floor", [False, True])
def test_no_animals_preserves_parent_forecast_and_artifact_entrypoint(floor):
    digest = FLOOR_CONTROL if floor else CONTROL
    raw = gzip.decompress(Path(f"reports/sources/{digest}.py.gz").read_bytes())
    assert hashlib.sha256(raw).hexdigest() == digest
    parent, candidate = {}, {}
    exec(raw, parent)
    source = build(floor_forecast=floor)
    exec(source, candidate)
    assert get_last_callable(source).__code__ == candidate["agent"].__code__
    env = make("kaggriculture", configuration={"seed": 5007})
    env.reset()
    for seat in (0, 1):
        obs = deepcopy(env._Environment__get_shared_state(seat).observation)
        obs.update(day=9, hour=0, step=216)
        args = (obs, candidate["CROPS"], candidate["ANIMALS"], candidate["SHOPS"])
        assert candidate["forecast_inventory"](*args) == parent["forecast_inventory"](*args)


@pytest.mark.parametrize("floor", [False, True])
def test_clean_artifact_matches_source_with_public_opponent_care_bank(tmp_path, floor):
    source = build(floor_forecast=floor)
    env = make("kaggriculture", configuration={"seed": 5007})
    env.reset()
    obs = deepcopy(env._Environment__get_shared_state(0).observation)
    obs.update(day=9, hour=2, step=218)
    cow = game._new_animal("COW", 2)
    cow.update(pending_care_bonus=5, cared_today=True, fed_today=True)
    obs["farms"][1]["tiles"][0][0] = cow
    before = deepcopy(obs)
    expected = get_last_callable(source)(obs, env.configuration)
    assert obs == before
    artifact = tmp_path / "main.py"
    artifact.write_text(source, encoding="utf-8")
    script = "import json,runpy,sys; n=runpy.run_path(sys.argv[1]); o,c=json.load(sys.stdin); print(json.dumps(n['agent'](o,c)))"
    result = subprocess.run(
        [sys.executable, "-I", "-S", "-c", script, str(artifact)],
        input=json.dumps([obs, dict(env.configuration)]),
        capture_output=True,
        text=True,
        check=True,
        cwd=tmp_path,
    )
    assert not result.stderr
    assert json.loads(result.stdout) == expected
