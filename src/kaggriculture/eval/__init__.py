"""Evaluation harness: parallel episode runner, rating, A/B testing."""

from kaggriculture.eval.runner import (
    EpisodeResult,
    run_episode,
    run_pairing,
    summarize,
)

__all__ = [
    "EpisodeResult",
    "run_episode",
    "run_pairing",
    "summarize",
]
