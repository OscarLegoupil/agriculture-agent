"""Evaluation harness: parallel episode runner, replay logging, metrics, rating, A/B testing."""

from kaggriculture.eval.logger import (
    iter_replays,
    load_replay,
    new_run_id,
    read_manifest,
    write_manifest,
)
from kaggriculture.eval.metrics import (
    collect_metrics,
    extract_metrics,
    flatten_row,
)
from kaggriculture.eval.rating import (
    Match,
    bradley_terry_fit,
    bradley_terry_to_elo_scale,
    elo_expected,
    elo_ratings,
    elo_trajectory,
    elo_update,
    episodes_to_matches,
)
from kaggriculture.eval.runner import (
    EpisodeResult,
    run_episode,
    run_pairing,
    summarize,
)

__all__ = [
    "EpisodeResult",
    "Match",
    "bradley_terry_fit",
    "bradley_terry_to_elo_scale",
    "collect_metrics",
    "elo_expected",
    "elo_ratings",
    "elo_trajectory",
    "elo_update",
    "episodes_to_matches",
    "extract_metrics",
    "flatten_row",
    "iter_replays",
    "load_replay",
    "new_run_id",
    "read_manifest",
    "run_episode",
    "run_pairing",
    "summarize",
    "write_manifest",
]
