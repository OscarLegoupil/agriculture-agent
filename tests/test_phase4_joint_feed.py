"""Joint feed feasibility uses distinct worker and depot resources."""

from copy import deepcopy

import pytest
from kaggle_environments import make
from kaggle_environments.envs.kaggriculture import kaggriculture as game
from scripts.phase4_joint_feed import build, joint_feed_routes


def witness():
    farm = game._new_farm(10, 10779)
    farm["farmer"] = [4, 3]
    farm["hands"] = [[4, 1]]
    for y in (0, 1):
        animal = game._new_animal("SHEEP", 0)
        animal.update(pending_care_bonus=3)
        farm["tiles"][y][4] = animal
    private = {"shed": {"WHEAT": 1}, "seeds": {}, "inventories": [{}, {"WHEAT": 1}]}
    return farm, private


def routes(farm, private, budget=1):
    return joint_feed_routes(
        {(4, 0), (4, 1)},
        [farm["farmer"], *farm["hands"]],
        private["inventories"],
        private["shed"],
        farm["tiles"],
        farm,
        {},
        18,
        [(4, 4), (4, 5), (5, 4), (5, 5)],
        budget=budget,
    )


def test_joint_assignment_exposes_departure_hidden_by_shared_nearest_worker():
    farm, private = witness()
    selected = routes(farm, private)
    assert len(selected) == 2
    assert len({route[1] for _, route in selected}) == 2
    assert sum(route[3] for _, route in selected) == 1
    assert min(route[-1] for _, route in selected) <= 1
    from scripts.phase4_joint_diagnostic import path

    actions = {}
    for target, (_, worker, home, fetching, _) in selected:
        current = tuple([farm["farmer"], *farm["hands"]][worker])
        sequence = []
        if fetching:
            sequence.extend(path(current, tuple(home), 10))
            sequence.append(("PICKUP", "WHEAT", 1))
            current = tuple(home)
        sequence.extend(path(current, target, 10))
        sequence.append(("FEED",))
        actions[worker] = sequence
    for hour in range(6):
        for worker in sorted(actions):
            sequence = actions[worker]
            action = sequence[hour] if hour < len(sequence) else ("PASS",)
            game._apply_unit_action(farm, private, worker, list(action), 10, 11, 24, 100)
    game._daily_refresh_animals(farm, 11)
    assert [farm["tiles"][y][4]["yield_units"] for y in (0, 1)] == [4, 4]


def test_depot_budget_escape_priority_and_existing_cargo_guard():
    farm, private = witness()
    private["shed"]["WHEAT"] = 0
    farm["tiles"][0][4]["consecutive_unfed"] = 1
    selected = routes(farm, private)
    assert len(selected) == 1 and selected[0][0] == (4, 0)
    private["inventories"][1]["MILK"] = 100
    assert routes(farm, private) == []


def test_budget_has_visible_fallback_without_mutating_inputs(capsys):
    farm, private = witness()
    before = deepcopy((farm, private))
    assert routes(farm, private, budget=0) is None
    assert "joint_feed_fallback: budget" in capsys.readouterr().err
    assert (farm, private) == before


@pytest.mark.parametrize("base", ["banked", "depot"])
def test_candidate_build_contains_joint_assignment_and_original_fallback(base):
    namespace = {}
    exec(build(base), namespace)
    assert callable(namespace["agent"])
    assert "joint_routes is None" in build(base)


def test_repeated_policy_decisions_finish_both_official_feed_obligations():
    env = make("kaggriculture", configuration={"seed": 0})
    env.reset()
    obs = deepcopy(env.state[0].observation)
    farm, private = witness()
    obs["farms"][0] = farm
    obs["private"] = private
    obs["market"]["prices"]["WOOL"] = 164
    obs["market"]["prices"]["WHEAT"] = 36
    namespace = {}
    exec(build("banked"), namespace)
    for hour in range(18, 24):
        obs.update(day=11, hour=hour, step=11 * 24 + hour, player=0)
        decision = namespace["agent"](obs, dict(env.configuration))
        for worker, action in enumerate([decision["farmer"], *decision["hands"]]):
            game._apply_unit_action(farm, private, worker, action, 10, 11, 24, 100)
    game._daily_refresh_animals(farm, 11)
    assert [farm["tiles"][y][4]["yield_units"] for y in (0, 1)] == [4, 4]
