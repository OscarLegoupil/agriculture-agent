"""Evaluation harness: parallel episode runner, replay logging, rating, A/B testing."""

from kaggriculture.eval.logger import (
    iter_replays,
    load_replay,
    new_run_id,
    read_manifest,
    write_manifest,
)
from kaggriculture.eval.runner import (
    EpisodeResult,
    run_episode,
    run_pairing,
    summarize,
)

__all__ = [
    "EpisodeResult",
    "iter_replays",
    "load_replay",
    "new_run_id",
    "read_manifest",
    "run_episode",
    "run_pairing",
    "summarize",
    "write_manifest",
]
