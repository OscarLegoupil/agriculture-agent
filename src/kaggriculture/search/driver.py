"""M7-d driver: beam search for the best route parameters against a fixed
opponent family, then persist the winner as a tuned route YAML.

Usage (run from repo root):

    uv run python -m kaggriculture.search.driver \
        --family v4_micro \
        --opponent src/kaggriculture/agent/route_agent/agent_v4_micro.py \
        --eval-seeds 20 --beam-width 2 --iterations 2

The tuned YAML lands at ``configs/routes/tuned/<family>.yaml``. Every
evaluated candidate is logged as a nested MLflow run.
"""

from __future__ import annotations

import argparse
import time
from pathlib import Path
from typing import Any

import yaml

from kaggriculture.search.beam import (
    GridSpec,
    beam_search,
    dict_neighbours,
    dict_to_tuple,
    tuple_to_dict,
)
from kaggriculture.search.evaluate import evaluate_config

_BASE_YAML = """
name: v4_baseline
description: v4 port used as the search center.
crops:
  - {tile: [3, 4], crop: WHEAT}
  - {tile: [4, 4], crop: CARROT}
  - {tile: [3, 3], crop: CARROT}
structures:
  - {tile: [4, 3], kind: COOP, animal: GOOSE}
hand:
  primary_tiles: [[3, 3]]
  fallback_tiles: [[4, 4], [3, 4]]
land_buys: []
market_policy:
  seed_buy_order: [WHEAT, CARROT]
  animal_buy_order: [GOOSE]
  hire:
    from_day: 3
    per_day: 1
    price_cap: 10
  feed_stockpiles:
    - {product: WHEAT, for_animal: GOOSE, buy_below: 20, cap: 10, reserve: 2}
  sell_order: [WHEAT, CARROT, EGG, FERTILIZER]
  sell_min_price:
    WHEAT: 25
    CARROT: 35
    EGG: 50
    FERTILIZER: 90
  liquidate_from_day: 29
  shed_high_water: 80
"""

_GRIDS: dict[str, GridSpec] = {
    "tail_start_day": GridSpec("tail_start_day", (20, 22, 24, 25)),
    "salvage_ratio": GridSpec("salvage_ratio", (0.80, 0.85, 0.90)),
    "drop_ratio": GridSpec("drop_ratio", (0.65, 0.70, 0.75)),
    "tail_floor": GridSpec("tail_floor", (3, 5, 7)),
    "liquidate_from_day": GridSpec("liquidate_from_day", (26, 27, 28, 29)),
    "shed_high_water": GridSpec("shed_high_water", (30, 40, 60, 80)),
}

_INITIAL = {
    "tail_start_day": 22,
    "salvage_ratio": 0.85,
    "drop_ratio": 0.70,
    "tail_floor": 5,
    "liquidate_from_day": 27,
    "shed_high_water": 40,
}

_MICRO_KEYS = ("tail_start_day", "salvage_ratio", "drop_ratio", "tail_floor")
_ROUTE_KEYS = ("liquidate_from_day", "shed_high_water")


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    ap = argparse.ArgumentParser(prog="kagg-search")
    ap.add_argument("--family", default="v4_micro", help="Opponent-family cache key")
    ap.add_argument(
        "--opponent",
        default="src/kaggriculture/agent/route_agent/agent_v4_micro.py",
        help="Path to the opponent agent .py used for evaluation",
    )
    ap.add_argument("--eval-seeds", type=int, default=20, help="Seeds per candidate (with swap)")
    ap.add_argument("--beam-width", type=int, default=2)
    ap.add_argument("--iterations", type=int, default=2)
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument(
        "--out-dir",
        type=Path,
        default=Path("configs") / "routes" / "tuned",
        help="Where to write the tuned YAML",
    )
    ap.add_argument("--mlflow", action="store_true", help="Log the search run to MLflow")
    return ap.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = _parse_args(argv)
    seeds = list(range(args.eval_seeds))

    def evaluate(state: Any) -> float:
        cfg = tuple_to_dict(state)
        micro_kwargs = {k: cfg[k] for k in _MICRO_KEYS}
        route_overrides = {k: cfg[k] for k in _ROUTE_KEYS}
        yaml_text = _yaml_with_overrides(_BASE_YAML, route_overrides)
        res = evaluate_config(
            yaml_text=yaml_text,
            micro_kwargs=micro_kwargs,
            opponent_agent_path=args.opponent,
            seeds=seeds,
            workers=args.workers,
        )
        print(
            f"  cfg={cfg}  n={res.n}  wins={res.wins_a}-{res.wins_b}  "
            f"score={res.score:+.3f}  gap={res.mean_gap:+.1f}"
        )
        return res.score

    def nbs(state: Any) -> list[Any]:
        s = tuple_to_dict(state)
        return [dict_to_tuple(n) for n in dict_neighbours(s, _GRIDS)]

    t0 = time.perf_counter()
    initial_state = dict_to_tuple(_INITIAL)
    best, trace = beam_search(
        [initial_state],
        nbs,
        evaluate,
        beam_width=args.beam_width,
        max_iterations=args.iterations,
    )
    duration = time.perf_counter() - t0
    best_cfg = tuple_to_dict(best)  # type: ignore[arg-type]
    print(f"\nBEST cfg={best_cfg}  evaluations={len(trace)}  duration={duration:.1f}s")

    tuned_path = _write_tuned_yaml(args.out_dir, args.family, best_cfg)
    print(f"Wrote tuned route to {tuned_path}")

    if args.mlflow:
        _log_to_mlflow(args, trace, best_cfg, duration)


def _yaml_with_overrides(base_yaml_text: str, overrides: dict[str, Any]) -> str:
    """Apply ``liquidate_from_day`` / ``shed_high_water`` overrides to the
    base YAML and return the serialized text."""
    doc = yaml.safe_load(base_yaml_text)
    mp = doc.setdefault("market_policy", {})
    if "liquidate_from_day" in overrides:
        mp["liquidate_from_day"] = int(overrides["liquidate_from_day"])
    if "shed_high_water" in overrides:
        mp["shed_high_water"] = int(overrides["shed_high_water"])
    return yaml.safe_dump(doc, sort_keys=False)


def _write_tuned_yaml(out_dir: Path, family: str, cfg: dict[str, Any]) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    base = yaml.safe_load(_BASE_YAML)
    base["name"] = f"tuned_{family}"
    base["description"] = f"Tuned against opponent family '{family}' via beam search."
    mp = base["market_policy"]
    mp["liquidate_from_day"] = int(cfg["liquidate_from_day"])
    mp["shed_high_water"] = int(cfg["shed_high_water"])
    base["micro"] = {
        "tail_start_day": int(cfg["tail_start_day"]),
        "salvage_ratio": float(cfg["salvage_ratio"]),
        "drop_ratio": float(cfg["drop_ratio"]),
        "tail_floor": int(cfg["tail_floor"]),
    }
    out = out_dir / f"{family}.yaml"
    out.write_text(yaml.safe_dump(base, sort_keys=False), encoding="utf-8")
    return out


def _log_to_mlflow(
    args: argparse.Namespace, trace: list[Any], best: dict[str, Any], duration: float
) -> None:
    import mlflow

    mlflow.set_experiment("kaggriculture")
    with mlflow.start_run(
        tags={"milestone": "M7-d", "issue": "56", "opponent_family": args.family}
    ):
        mlflow.log_params(
            {
                "family": args.family,
                "opponent": args.opponent,
                "eval_seeds": args.eval_seeds,
                "beam_width": args.beam_width,
                "iterations": args.iterations,
                "n_candidates_evaluated": len(trace),
            }
        )
        for k, v in best.items():
            mlflow.log_param(f"best_{k}", v)
        best_score = max(s.score for s in trace)
        mlflow.log_metrics({"best_score": best_score, "duration_seconds": duration})


if __name__ == "__main__":
    main()
