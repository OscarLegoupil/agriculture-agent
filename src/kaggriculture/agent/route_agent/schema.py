"""Dataclasses that describe a route.

A route is a strategic plan for one 720-turn episode: which tiles carry which
crops, where the coop or pasture goes, when to hire, when to buy land, market
buy and sell policy, and an optional list of explicit per-turn overrides that
short-circuit the generic runner logic on specific turns.

The runner replays a route deterministically given an observation: no I/O, no
hidden state, only the parsed `Route`.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True, slots=True)
class CropAssignment:
    """One tile is planted with `crop` throughout the episode."""

    tile: tuple[int, int]
    crop: str


@dataclass(frozen=True, slots=True)
class StructureAssignment:
    """One tile hosts a coop or pasture with a specific animal."""

    tile: tuple[int, int]
    kind: str  # "COOP" or "PASTURE"
    animal: str  # "GOOSE", "COW", "SHEEP"


@dataclass(frozen=True, slots=True)
class HireSchedule:
    """Hire N hands per day starting on `from_day`, up to a per-turn price cap."""

    from_day: int
    per_day: int
    price_cap: int


@dataclass(frozen=True, slots=True)
class LandBuy:
    """Buy a quadrant once the money buffer allows it, on or after `from_day`."""

    quadrant: str  # "NE", "SW", "SE"
    money_buffer: int
    from_day: int


@dataclass(frozen=True, slots=True)
class FeedStockpile:
    """Buy `product` while `for_animal` is placed and stockpile is under `cap`."""

    product: str
    for_animal: str
    buy_below: int
    cap: int
    reserve: int


@dataclass(frozen=True, slots=True)
class MarketPolicy:
    """Buy / sell rules consumed each turn.

    `seed_buy_order`, `animal_buy_order`, and `sell_order` control the exact
    order market entries appear in the returned action dict; this matters when
    the simulator processes queued market actions in order.
    """

    seed_buy_order: tuple[str, ...]
    animal_buy_order: tuple[str, ...]
    hire: HireSchedule | None
    feed_stockpiles: tuple[FeedStockpile, ...]
    sell_order: tuple[str, ...]
    sell_min_price: dict[str, int]
    liquidate_from_day: int
    shed_high_water: int


@dataclass(frozen=True, slots=True)
class HandAssignment:
    """Priority tiles for a hand, resolved by index in `Route.crops` list."""

    primary_tiles: tuple[tuple[int, int], ...]
    fallback_tiles: tuple[tuple[int, int], ...]


@dataclass(frozen=True, slots=True)
class RouteOverride:
    """Force `unit` to take `action` on `turn`. Unused by v4; wired for later routes."""

    turn: int
    unit: str  # "farmer" or "hand:<index>"
    action: list[Any]


@dataclass(frozen=True, slots=True)
class Route:
    name: str
    description: str
    crops: tuple[CropAssignment, ...]
    structures: tuple[StructureAssignment, ...]
    hand: HandAssignment
    land_buys: tuple[LandBuy, ...]
    market_policy: MarketPolicy
    overrides: tuple[RouteOverride, ...] = field(default_factory=tuple)
