"""Tests for the action legality checker.

Legit actions produce zero issues. Illegal actions produce specific, useful
reasons. A real episode of `random` vs `pass` accumulates a nonzero number of
issues (random makes plenty of no-op moves).
"""

from __future__ import annotations

from kaggle_environments import make

from kaggriculture.env import Observation, actions, check


def _obs_at_start(seed: int = 7) -> Observation:
    env = make("kaggriculture", configuration={"episodeSteps": 1, "seed": seed})
    env.run(["pass", "pass"])
    raw = dict(env.steps[0][0].observation)
    raw["player"] = 0
    return Observation.from_dict(raw)


def test_pass_action_has_no_issues() -> None:
    obs = _obs_at_start()
    assert check(obs, actions.action()) == []


def test_hand_action_without_hand_flagged() -> None:
    obs = _obs_at_start()
    # Main farmer has no hands on day 0, so two hand ops are both invalid.
    issues = check(obs, actions.action(hands=[actions.pass_(), actions.pass_()]))
    assert len(issues) == 2
    assert all("no hand at index" in i.reason for i in issues)


def test_plant_without_seed_flagged() -> None:
    obs = _obs_at_start()
    # seeds dict starts empty (all counts 0), so PLANT WHEAT is invalid.
    issues = check(obs, actions.action(farmer=actions.plant("WHEAT")))
    assert len(issues) == 1
    assert "no WHEAT seeds" in issues[0].reason


def test_plant_atomic_drop_when_demand_exceeds_seeds() -> None:
    obs = _obs_at_start()
    # We synthesise the scenario: 1 seed, 2 PLANT demands. Since we cannot mutate
    # the frozen Observation, we construct one manually with a single seed.
    from dataclasses import replace

    priv = replace(obs.private, seeds={**obs.private.seeds, "WHEAT": 1})
    obs2 = replace(obs, private=priv)

    issues = check(
        obs2,
        actions.action(
            farmer=actions.plant("WHEAT"),
            hands=[actions.plant("WHEAT")],
        ),
    )
    # Both units should be flagged with the atomic drop reason (they should not
    # count as separate "no seeds" failures).
    assert len(issues) == 2
    assert all("demand (2) exceeds seed count (1)" in i.reason for i in issues)


def test_sell_without_stock_flagged() -> None:
    obs = _obs_at_start()
    issues = check(obs, actions.action(market=[actions.sell("WHEAT", 3)]))
    assert len(issues) == 1
    assert "no WHEAT in shed" in issues[0].reason


def test_buy_land_when_all_owned_flagged() -> None:
    from dataclasses import replace

    obs = _obs_at_start()
    farm = replace(obs.me, unlocked_quadrants=("NW", "NE", "SW", "SE"), money=100_000.0)
    farms = tuple(farm if i == obs.player else f for i, f in enumerate(obs.farms))
    obs2 = replace(obs, farms=farms)

    issues = check(obs2, actions.action(market=[actions.buy_land()]))
    assert len(issues) == 1
    assert "all quadrants already unlocked" in issues[0].reason


def test_hire_without_money_flagged() -> None:
    from dataclasses import replace

    obs = _obs_at_start()
    farm = replace(obs.me, money=0.0)
    farms = tuple(farm if i == obs.player else f for i, f in enumerate(obs.farms))
    obs2 = replace(obs, farms=farms)

    issues = check(obs2, actions.action(market=[actions.hire()]))
    assert len(issues) == 1
    assert "HIRE cost" in issues[0].reason


def test_random_agent_accumulates_issues_over_episode() -> None:
    env = make("kaggriculture", configuration={"episodeSteps": 48, "seed": 0})
    env.run(["random", "pass"])

    total_issues = 0
    for step in env.steps:
        raw = dict(step[0].observation)
        raw["player"] = 0
        try:
            obs = Observation.from_dict(raw)
        except (KeyError, TypeError):
            continue
        # We can only see the action once the env records it on the state.
        act = step[0].action or {}
        if not isinstance(act, dict) or not act:
            continue
        total_issues += len(check(obs, act))

    # `random` produces many no-op moves; a 48-turn episode should log at least a handful.
    assert total_issues > 0
