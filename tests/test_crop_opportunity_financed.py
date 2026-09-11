"""Funding, shared-stock and official commissioning contracts for crop admission."""

import hashlib
import json
import subprocess
import sys
from collections import Counter
from copy import deepcopy

import pytest
from experiments.crop_opportunity import build as parent_build
from experiments.crop_opportunity_financed import INCUMBENT, build, financed_crop_values
from kaggle_environments import make
from kaggle_environments.agent import get_last_callable


def test_frozen_parent_and_official_entrypoint():
    assert hashlib.sha256(parent_build(start_day=3).encode()).hexdigest() == INCUMBENT
    assert get_last_callable(build()).__name__ == "agent"


def test_funding_uses_remaining_cash_and_reserves_actual_shared_seeds():
    scores = dict(STRAWBERRY=1000, WHEAT=600, CARROT=650)
    seeds = dict(WHEAT=4)
    admitted, purchases = Counter(STRAWBERRY=2), Counter(STRAWBERRY=2)
    # Two expensive seeds have already consumed the available investment cash.
    assert financed_crop_values(scores, seeds, admitted, 205, purchases, 3) == {"WHEAT": 600}
    admitted["WHEAT"] = 4
    assert financed_crop_values(scores, seeds, admitted, 205, purchases, 3) == {}
    # Reserved wheat is not mistaken for another task's free stock. New wheat
    # can be ordered only when its cost fits after the retained cash reserve.
    assert financed_crop_values(scores, seeds, admitted, 211, purchases, 3) == {"WHEAT": 600}
    purchases["WHEAT"] = 4
    assert financed_crop_values(scores, seeds, admitted, 211, purchases, 3) == {}


def test_financed_artifact_executes_without_repository_imports(tmp_path):
    source = build()
    env = make("kaggriculture", configuration={"seed": 5007})
    env.reset()
    observation = env._Environment__get_shared_state(0).observation
    before = deepcopy(observation)
    expected = get_last_callable(source)(observation, env.configuration)
    assert observation == before
    artifact = tmp_path / "main.py"
    artifact.write_text(source, encoding="utf-8")
    script = "import json,runpy,sys; n=runpy.run_path(sys.argv[1]); o,c=json.load(sys.stdin); print(json.dumps(n['agent'](o,c)))"
    result = subprocess.run(
        [sys.executable, "-I", "-S", "-c", script, str(artifact)],
        input=json.dumps([observation, dict(env.configuration)]),
        text=True,
        capture_output=True,
        check=True,
        cwd=tmp_path,
    )
    assert not result.stderr
    assert json.loads(result.stdout) == expected


def prefix(source, seat):
    agent = get_last_callable(source)
    opponent = get_last_callable(parent_build("incumbent"))
    env = make("kaggriculture", configuration={"seed": 5007})
    env.reset()
    actions, born = [], Counter()
    failures = deaths = escapes = 0
    for index in range(120):
        if index == 72:
            # Controlled post-harvest liquidity witness matching the recorded
            # seed-5007 capital/seed constraint, independent of external code.
            farm = env.state[0].observation.farms[seat]
            farm["money"] = 508
            for row in farm["tiles"]:
                for x, tile in enumerate(row):
                    if isinstance(tile, dict) and tile.get("crop") == "WHEAT":
                        row[x] = None
            env.state[seat].observation.private["seeds"]["WHEAT"] = 4
        views = [env._Environment__get_shared_state(player).observation for player in (0, 1)]
        before = deepcopy(views[seat]["farms"][seat])
        positions = [before["farmer"], *before["hands"]]
        action = agent(views[seat], env.configuration)
        other = opponent(views[1 - seat], env.configuration)
        work = [action["farmer"], *action["hands"]]
        requested = Counter(row[1] for row in work if row[0] == "PLANT")
        assert all(
            n <= views[seat]["private"]["seeds"].get(crop, 0) for crop, n in requested.items()
        )
        env.step([action, other] if seat == 0 else [other, action])
        after = env._Environment__get_shared_state(seat).observation["farms"][seat]
        for position, task in zip(positions, work, strict=True):
            if task[0] == "PLANT":
                tile = after["tiles"][position[1]][position[0]]
                success = isinstance(tile, dict) and tile.get("crop") == task[1]
                failures += not success
                if success and index >= 72:
                    born[task[1]] += 1
        for y, row in enumerate(after["tiles"]):
            for x, tile in enumerate(row):
                old = before["tiles"][y][x]
                if isinstance(old, dict):
                    deaths += (
                        old.get("kind") == "PLANT"
                        and isinstance(tile, dict)
                        and tile.get("kind") == "WEED"
                    )
                    escapes += "animal" in old and not (isinstance(tile, dict) and "animal" in tile)
        actions.append(action)
        assert all(row.status == "ACTIVE" for row in env.state)
    return actions, born, failures, deaths, escapes


@pytest.mark.parametrize("seat", [0, 1])
def test_official_day3_commissions_owned_wheat_after_budget_binds(seat):
    old, old_born, *_ = prefix(parent_build(start_day=3), seat)
    actions, born, failures, deaths, escapes = prefix(build(), seat)
    assert actions[:72] == old[:72]
    assert old_born["WHEAT"] == 0
    assert born["WHEAT"] >= 3
    assert born["STRAWBERRY"] > 0
    assert failures == deaths == escapes == 0
