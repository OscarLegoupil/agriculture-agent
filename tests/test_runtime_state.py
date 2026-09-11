"""Verify lifecycle semantics of the official Python HTTP action runner."""

from copy import deepcopy
from types import SimpleNamespace

from kaggle_environments import main, make


def test_official_action_endpoint_preserves_episode_state_and_disposes_it(monkeypatch):
    env = make("kaggriculture", configuration={"seed": 5000})
    env.reset(2)
    source = """
calls = 0
def agent(obs, cfg):
    global calls
    calls += 1
    return {"farmer": ["PASS"], "hands": [], "market": [], "calls": calls}
"""
    monkeypatch.setattr(main, "cached_agent", None)
    monkeypatch.setattr(main, "disposed", False)
    request = SimpleNamespace(
        agents=[source],
        environment="kaggriculture",
        configuration=dict(env.configuration),
        info={},
        state={"observation": deepcopy(env.state[0].observation)},
        debug=False,
        log_path=None,
    )
    assert main.action_act(request)["action"]["calls"] == 1
    assert main.action_act(request)["action"]["calls"] == 2
    main.action_dispose(request)
    assert main.action_act(request)["action"]["calls"] == 1
