"""Verify the tuned YAML artifact from the beam search loads cleanly.

M7-d writes ``configs/routes/tuned/<family>.yaml`` with an embedded
``micro`` block; the runtime must read it and apply the tuned parameters
without any extra plumbing. This test guards that contract.
"""

from __future__ import annotations

from pathlib import Path

from kaggriculture.agent.route_agent.loader import load_route
from kaggriculture.agent.route_agent.micro import micro_agent_from_yaml

_TUNED_V4_MICRO = (
    Path(__file__).resolve().parents[2] / "configs" / "routes" / "tuned" / "v4_micro.yaml"
)


def test_tuned_v4_micro_yaml_contains_micro_block() -> None:
    route = load_route(_TUNED_V4_MICRO)
    assert route.name == "tuned_v4_micro"
    kwargs = route.micro.as_kwargs()
    assert kwargs["tail_start_day"] == 22
    assert 0.7 <= kwargs["salvage_ratio"] <= 1.0
    assert route.market_policy.liquidate_from_day <= 29


def test_micro_agent_from_yaml_applies_tuned_micro() -> None:
    fn = micro_agent_from_yaml(_TUNED_V4_MICRO)
    ctrl = fn.controller  # type: ignore[attr-defined]
    assert ctrl.tail_start_day == 22
