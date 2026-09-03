"""YAML loader for route configs stored in ``configs/routes/``."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from kaggriculture.agent.route_agent.schema import (
    CropAssignment,
    FeedStockpile,
    HandAssignment,
    HireSchedule,
    LandBuy,
    MarketPolicy,
    MicroParams,
    Route,
    RouteOverride,
    StructureAssignment,
)


def _tile(raw: Any) -> tuple[int, int]:
    if not isinstance(raw, list) or len(raw) != 2:
        raise ValueError(f"tile must be a 2-list [x, y], got {raw!r}")
    return int(raw[0]), int(raw[1])


def _tiles(raw: Any) -> tuple[tuple[int, int], ...]:
    if raw is None:
        return ()
    if not isinstance(raw, list):
        raise ValueError(f"expected list of tiles, got {raw!r}")
    return tuple(_tile(t) for t in raw)


def load_route(path: str | Path) -> Route:
    with open(path, encoding="utf-8") as fh:
        raw = yaml.safe_load(fh)
    return route_from_dict(raw)


def route_from_dict(raw: dict[str, Any]) -> Route:
    crops = tuple(
        CropAssignment(tile=_tile(c["tile"]), crop=str(c["crop"])) for c in raw.get("crops", [])
    )
    structures = tuple(
        StructureAssignment(
            tile=_tile(s["tile"]),
            kind=str(s["kind"]),
            animal=str(s["animal"]),
        )
        for s in raw.get("structures", [])
    )
    hand_raw = raw.get("hand", {}) or {}
    hand = HandAssignment(
        primary_tiles=_tiles(hand_raw.get("primary_tiles")),
        fallback_tiles=_tiles(hand_raw.get("fallback_tiles")),
    )
    land_buys = tuple(
        LandBuy(
            quadrant=str(lb["quadrant"]),
            money_buffer=int(lb["money_buffer"]),
            from_day=int(lb["from_day"]),
        )
        for lb in raw.get("land_buys", [])
    )
    market_policy = _market_policy(raw.get("market_policy", {}) or {})
    overrides = tuple(
        RouteOverride(turn=int(o["turn"]), unit=str(o["unit"]), action=list(o["action"]))
        for o in raw.get("overrides", [])
    )
    micro = _micro_params(raw.get("micro", {}) or {})
    return Route(
        name=str(raw["name"]),
        description=str(raw.get("description", "")),
        crops=crops,
        structures=structures,
        hand=hand,
        land_buys=land_buys,
        market_policy=market_policy,
        overrides=overrides,
        micro=micro,
    )


def _micro_params(raw: dict[str, Any]) -> MicroParams:
    def _int(k: str) -> int | None:
        return int(raw[k]) if k in raw and raw[k] is not None else None

    def _float(k: str) -> float | None:
        return float(raw[k]) if k in raw and raw[k] is not None else None

    return MicroParams(
        tail_start_day=_int("tail_start_day"),
        tail_floor=_int("tail_floor"),
        salvage_ratio=_float("salvage_ratio"),
        drop_ratio=_float("drop_ratio"),
        min_current_price=_int("min_current_price"),
        lookahead_days=_int("lookahead_days"),
    )


def _market_policy(raw: dict[str, Any]) -> MarketPolicy:
    hire_raw = raw.get("hire")
    hire: HireSchedule | None = None
    if hire_raw is not None:
        hire = HireSchedule(
            from_day=int(hire_raw["from_day"]),
            per_day=int(hire_raw["per_day"]),
            price_cap=int(hire_raw["price_cap"]),
        )
    feed_stockpiles = tuple(
        FeedStockpile(
            product=str(fs["product"]),
            for_animal=str(fs["for_animal"]),
            buy_below=int(fs["buy_below"]),
            cap=int(fs["cap"]),
            reserve=int(fs["reserve"]),
        )
        for fs in raw.get("feed_stockpiles", [])
    )
    return MarketPolicy(
        seed_buy_order=tuple(str(s) for s in raw.get("seed_buy_order", [])),
        animal_buy_order=tuple(str(a) for a in raw.get("animal_buy_order", [])),
        hire=hire,
        feed_stockpiles=feed_stockpiles,
        sell_order=tuple(str(s) for s in raw.get("sell_order", [])),
        sell_min_price={str(k): int(v) for k, v in raw.get("sell_min_price", {}).items()},
        liquidate_from_day=int(raw.get("liquidate_from_day", 999)),
        shed_high_water=int(raw.get("shed_high_water", 10_000)),
    )
