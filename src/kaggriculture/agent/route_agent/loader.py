"""YAML loader and writer for route configs stored in ``configs/routes/``."""

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
    Phase,
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


def _crops(raw: Any) -> tuple[CropAssignment, ...]:
    return tuple(CropAssignment(tile=_tile(c["tile"]), crop=str(c["crop"])) for c in raw or [])


def _structures(raw: Any) -> tuple[StructureAssignment, ...]:
    return tuple(
        StructureAssignment(
            tile=_tile(s["tile"]),
            kind=str(s["kind"]),
            animal=str(s["animal"]),
        )
        for s in raw or []
    )


def _phases(raw: Any) -> tuple[Phase, ...]:
    phases = tuple(
        Phase(
            from_day=int(p["from_day"]),
            crops=_crops(p.get("crops")),
            structures=_structures(p.get("structures")),
            hands=int(p.get("hands", 0)),
            fertilize=tuple(str(c) for c in p.get("fertilize", [])),
        )
        for p in raw or []
    )
    days = [p.from_day for p in phases]
    if days != sorted(days) or len(set(days)) != len(days):
        raise ValueError(f"phases must have strictly increasing from_day, got {days}")
    return phases


def route_from_dict(raw: dict[str, Any]) -> Route:
    crops = _crops(raw.get("crops"))
    structures = _structures(raw.get("structures"))
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
        phases=_phases(raw.get("phases")),
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
        money_reserve=int(raw.get("money_reserve", 0)),
        feed_days=int(raw.get("feed_days", 3)),
    )


def route_to_dict(route: Route) -> dict[str, Any]:
    """Serialize a `Route` back to the mapping `route_from_dict` accepts."""
    mp = route.market_policy
    doc: dict[str, Any] = {
        "name": route.name,
        "description": route.description,
        "crops": [{"tile": list(c.tile), "crop": c.crop} for c in route.crops],
        "structures": [
            {"tile": list(s.tile), "kind": s.kind, "animal": s.animal} for s in route.structures
        ],
        "hand": {
            "primary_tiles": [list(t) for t in route.hand.primary_tiles],
            "fallback_tiles": [list(t) for t in route.hand.fallback_tiles],
        },
        "land_buys": [
            {"quadrant": lb.quadrant, "money_buffer": lb.money_buffer, "from_day": lb.from_day}
            for lb in route.land_buys
        ],
        "market_policy": {
            "seed_buy_order": list(mp.seed_buy_order),
            "animal_buy_order": list(mp.animal_buy_order),
            "feed_stockpiles": [
                {
                    "product": fs.product,
                    "for_animal": fs.for_animal,
                    "buy_below": fs.buy_below,
                    "cap": fs.cap,
                    "reserve": fs.reserve,
                }
                for fs in mp.feed_stockpiles
            ],
            "sell_order": list(mp.sell_order),
            "sell_min_price": dict(mp.sell_min_price),
            "liquidate_from_day": mp.liquidate_from_day,
            "shed_high_water": mp.shed_high_water,
            "money_reserve": mp.money_reserve,
            "feed_days": mp.feed_days,
        },
    }
    if mp.hire is not None:
        doc["market_policy"]["hire"] = {
            "from_day": mp.hire.from_day,
            "per_day": mp.hire.per_day,
            "price_cap": mp.hire.price_cap,
        }
    micro = route.micro.as_kwargs()
    if micro:
        doc["micro"] = micro
    if route.overrides:
        doc["overrides"] = [
            {"turn": o.turn, "unit": o.unit, "action": list(o.action)} for o in route.overrides
        ]
    if route.phases:
        doc["phases"] = [
            {
                "from_day": p.from_day,
                "hands": p.hands,
                "fertilize": list(p.fertilize),
                "structures": [
                    {"tile": list(s.tile), "kind": s.kind, "animal": s.animal} for s in p.structures
                ],
                "crops": [{"tile": list(c.tile), "crop": c.crop} for c in p.crops],
            }
            for p in route.phases
        ]
    return doc


def write_route(route: Route, path: str | Path) -> Path:
    """Write `route` to `path` as YAML and return the path."""
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(yaml.safe_dump(route_to_dict(route), sort_keys=False), encoding="utf-8")
    return out
