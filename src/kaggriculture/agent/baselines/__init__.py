"""Baseline agents (rule-based) for the internal Elo ladder.

Each baseline exercises one strategic axis and is designed to beat its
predecessor at a statistically significant margin. Import an agent for
in-process use, or point the runner at the file for Kaggle-style loading.
"""

from kaggriculture.agent.baselines.v0_wheat import agent as v0_wheat
from kaggriculture.agent.baselines.v1_mixed import agent as v1_mixed

__all__ = ["v0_wheat", "v1_mixed"]
