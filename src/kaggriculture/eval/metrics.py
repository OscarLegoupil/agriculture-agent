"""Per-episode metrics extraction from replay JSONs.

Given `env.toJSON()`-style replay, extract useful metrics for A/B analysis:
action histograms per player, sell volumes per resource, land expansion, hires,
final market state. `extract_metrics(replay)` returns a nested dict.
`flatten_row(m)` converts it to a flat dict suitable for a pandas DataFrame row.
"""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path
from typing import Any

from kaggriculture.env.constants import PRODUCTS
from kaggriculture.eval.logger import read_manifest


def _count_action_ops(actions_per_step: Iterable[Any], component: str) -> dict[str, int]:
    """Count occurrences of each op name in a stream of raw action dicts."""
    counts: dict[str, int] = {}
    for act in actions_per_step:
        if not isinstance(act, dict):
            continue
        ops = act.get(component)
        if ops is None:
            continue
        if component == "farmer":
            _bump_op(counts, ops)
        else:
            if not isinstance(ops, list):
                continue
            for op in ops:
                _bump_op(counts, op)
    return counts


def _bump_op(counts: dict[str, int], op: Any) -> None:
    if isinstance(op, list) and op:
        name = str(op[0])
        counts[name] = counts.get(name, 0) + 1


def _count_sells_per_resource(actions_per_step: Iterable[Any]) -> dict[str, int]:
    """Sum unit counts of SELL <product> <n> across all market orders."""
    sold: dict[str, int] = {}
    for act in actions_per_step:
        if not isinstance(act, dict):
            continue
        market = act.get("market")
        if not isinstance(market, list):
            continue
        for order in market:
            if isinstance(order, list) and len(order) >= 3 and order[0] == "SELL":
                item = str(order[1])
                try:
                    n = int(order[2])
                except (TypeError, ValueError):
                    continue
                sold[item] = sold.get(item, 0) + max(0, n)
    return sold


def extract_metrics(replay: dict[str, Any]) -> dict[str, Any]:
    """Compute a nested-dict summary of one episode."""
    steps = replay.get("steps", [])
    if not steps:
        return {}

    config = replay.get("configuration", {})
    n_players = len(steps[0])
    per_player_actions: list[list[Any]] = [[] for _ in range(n_players)]
    for step in steps[1:]:  # step 0 has no actions
        for pid, state in enumerate(step):
            act = state.get("action")
            if act is not None:
                per_player_actions[pid].append(act)

    final = steps[-1]
    first_obs = steps[0][0].get("observation", {})

    metrics: dict[str, Any] = {
        "n_steps": len(steps),
        "seed": (replay.get("info") or {}).get("seed"),
        "episode_id": replay.get("id"),
        "config": {k: config.get(k) for k in ("episodeSteps", "boardSize", "startingMoney")},
        "final_coins": [float(final[i].get("reward") or 0.0) for i in range(n_players)],
        "final_status": [str(final[i].get("status")) for i in range(n_players)],
    }

    # Winner
    a, b = metrics["final_coins"]
    metrics["winner"] = "tie" if a == b else ("0" if a > b else "1")
    metrics["coin_gap_0_minus_1"] = a - b

    # Action histograms
    metrics["farmer_ops"] = [
        _count_action_ops(per_player_actions[pid], "farmer") for pid in range(n_players)
    ]
    metrics["hand_ops"] = [
        _count_action_ops(per_player_actions[pid], "hands") for pid in range(n_players)
    ]
    metrics["market_ops"] = [
        _count_action_ops(per_player_actions[pid], "market") for pid in range(n_players)
    ]

    # Sell volumes per resource (unit counts requested; actual sold may be lower).
    metrics["sell_units_requested"] = [
        _count_sells_per_resource(per_player_actions[pid]) for pid in range(n_players)
    ]

    # End-of-episode farm state
    final_farms = final[0].get("observation", {}).get("farms") or first_obs.get("farms", [])
    if final_farms:
        metrics["final_quadrants"] = [len(f.get("unlocked_quadrants", ["NW"])) for f in final_farms]
    else:
        metrics["final_quadrants"] = [1] * n_players

    # Total hires: count HIRE market ops per player across the episode
    metrics["total_hires"] = [m.get("HIRE", 0) for m in metrics["market_ops"]]

    # Final market state
    final_market = final[0].get("observation", {}).get("market", {}) or first_obs.get("market", {})
    metrics["final_market_inventory"] = {
        p: int(final_market.get("inventory", {}).get(p, 0)) for p in PRODUCTS
    }
    metrics["final_market_prices"] = {
        p: int(final_market.get("prices", {}).get(p, 0)) for p in PRODUCTS
    }

    # Town shop composition at end
    final_town = final[0].get("observation", {}).get("town", {}) or first_obs.get("town", {})
    metrics["unlocked_shops"] = list(final_town.get("unlocked_shops", []))

    return metrics


def flatten_row(m: dict[str, Any]) -> dict[str, Any]:
    """Flatten a metrics dict to one row's worth of columns."""
    if not m:
        return {}
    row: dict[str, Any] = {
        "episode_id": m.get("episode_id"),
        "seed": m.get("seed"),
        "n_steps": m.get("n_steps"),
        "winner": m.get("winner"),
        "coin_gap_0_minus_1": m.get("coin_gap_0_minus_1"),
    }
    for pid in (0, 1):
        row[f"final_coins_{pid}"] = m["final_coins"][pid]
        row[f"final_status_{pid}"] = m["final_status"][pid]
        row[f"final_quadrants_{pid}"] = m["final_quadrants"][pid]
        row[f"total_hires_{pid}"] = m["total_hires"][pid]
        for op, count in m["farmer_ops"][pid].items():
            row[f"farmer_{op.lower()}_{pid}"] = count
        for op, count in m["market_ops"][pid].items():
            row[f"market_{op.lower()}_{pid}"] = count
        for product, units in m["sell_units_requested"][pid].items():
            row[f"sell_{product.lower()}_units_{pid}"] = units
    for product in PRODUCTS:
        row[f"final_inv_{product.lower()}"] = m["final_market_inventory"][product]
        row[f"final_price_{product.lower()}"] = m["final_market_prices"][product]
    row["shop_count"] = len(m["unlocked_shops"])
    return row


def collect_metrics(root: Path) -> list[dict[str, Any]]:
    """Extract metrics for every episode in a run directory."""
    import json

    rows: list[dict[str, Any]] = []
    for meta in read_manifest(root):
        replay_path = meta.get("replay_path")
        if not replay_path:
            continue
        with open(replay_path, encoding="utf-8") as fh:
            replay = json.load(fh)
        m = extract_metrics(replay)
        row = flatten_row(m)
        row["_seat_0"] = meta.get("seat_0")
        row["_agent_a"] = meta.get("agent_a")
        row["_agent_b"] = meta.get("agent_b")
        rows.append(row)
    return rows
