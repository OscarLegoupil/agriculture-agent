"""Offline route-parameter search.

Beam search over a small grid of micro-controller and route parameters,
evaluated with the M3 episode runner. The output is a tuned route YAML
per opponent family, stored under ``configs/routes/tuned/<family>.yaml``.

The search is intentionally lightweight: exhaustive grid search dominates
this parameter space at these budget levels, and beam search adds
guardrails when the space grows in later milestones. Both are
implemented here for parity.
"""

from kaggriculture.search.beam import BeamStep, beam_search
from kaggriculture.search.evaluate import EvalResult, evaluate_config

__all__ = ["BeamStep", "EvalResult", "beam_search", "evaluate_config"]
