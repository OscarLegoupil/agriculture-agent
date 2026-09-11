"""Benchmark adapter for phucthaiv02/kaggriculture; upstream policy unchanged."""

import sys
from pathlib import Path

_POLICIES = {}


def agent(observation, configuration=None):
    folder = str(Path(agent.__code__.co_filename).resolve().parent)
    if folder not in sys.path:
        sys.path.insert(0, folder)
    from agents.expansion_agent import make_agent

    seat = int(observation["player"])
    if seat not in _POLICIES or int(observation["step"]) == 0:
        _POLICIES[seat] = make_agent()
    return _POLICIES[seat](observation)
