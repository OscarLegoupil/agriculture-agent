"""A quick end-to-end check of the frozen standalone executable."""

from pathlib import Path

import pytest
from kaggle_environments import make


@pytest.mark.parametrize("seat", [0, 1])
def test_frozen_agent_smoke(seat):
    artifact = Path(__file__).resolve().parents[1] / "submissions/20260909-v7/main.py"
    environment = make("kaggriculture", configuration={"seed": 0})
    agents = [str(artifact), "starter"] if seat == 0 else ["starter", str(artifact)]
    environment.run(agents)
    assert environment.state[seat].status == "DONE"
    assert environment.state[seat].reward > 50_000
    assert not any(log[seat]["stderr"] for log in environment.logs if len(log) > seat)
