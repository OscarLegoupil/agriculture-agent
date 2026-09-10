"""Floor-priced durable products are held unless storage needs the room."""

import importlib
from copy import deepcopy
from pathlib import Path

from kaggle_environments import make


def _observation():
    env = make("kaggriculture", configuration={"seed": 0})
    env.reset()
    obs = deepcopy(env.state[0].observation)
    obs.update(day=15, hour=0, step=360, player=0)
    obs["farms"][0]["money"] = 10000
    obs["market"]["prices"]["STRAWBERRY"] = 1
    obs["private"] = {
        "shed": {"STRAWBERRY": 10},
        "seeds": {},
        "inventories": [{}],
    }
    return obs, env.configuration


def test_floor_holdback_preserves_space_and_terminal_sale(monkeypatch):
    root = Path(__file__).resolve().parents[1]
    monkeypatch.chdir(root)
    monkeypatch.syspath_prepend(str(root / "scripts"))
    namespace = {}
    exec(importlib.import_module("phase4_floor_holdback").build(), namespace)
    obs, config = _observation()
    action = namespace["agent"](deepcopy(obs), config)
    assert not any(order[:2] == ["SELL", "STRAWBERRY"] for order in action["market"])

    obs["private"]["shed"]["WHEAT"] = 80
    action = namespace["agent"](deepcopy(obs), config)
    assert any(order[:2] == ["SELL", "STRAWBERRY"] for order in action["market"])

    obs["day"] = 29
    obs["hour"] = 22
    action = namespace["agent"](deepcopy(obs), config)
    assert any(order[:2] == ["SELL", "STRAWBERRY"] for order in action["market"])
