"""Typed action builders.

The env accepts a per-turn action dict of the shape:

    {"farmer": [op, *args], "hands": [[op, *args], ...], "market": [[op, *args], ...]}

These builders return the correct list literals and let mypy catch typos on
op names, crops, animals, and products.
"""

from __future__ import annotations

from typing import Any, Literal, TypeAlias

Direction: TypeAlias = Literal["NORTH", "SOUTH", "EAST", "WEST"]
Crop: TypeAlias = Literal["WHEAT", "CARROT", "TOMATO", "STRAWBERRY", "MELON"]
Animal: TypeAlias = Literal["GOOSE", "COW", "SHEEP"]
Product: TypeAlias = Literal[
    "WHEAT",
    "CARROT",
    "TOMATO",
    "STRAWBERRY",
    "MELON",
    "EGG",
    "MILK",
    "WOOL",
    "FERTILIZER",
]
BuyableProduct: TypeAlias = Literal["WHEAT", "FERTILIZER"]
Item: TypeAlias = Product | Animal

UnitOp: TypeAlias = list[Any]
MarketOrder: TypeAlias = list[Any]
ActionDict: TypeAlias = dict[str, Any]


# Farmer / hand ops --------------------------------------------------------


def move(direction: Direction) -> UnitOp:
    return [direction]


def pass_() -> UnitOp:
    return ["PASS"]


def plant(crop: Crop) -> UnitOp:
    return ["PLANT", crop]


def water() -> UnitOp:
    return ["WATER"]


def harvest() -> UnitOp:
    return ["HARVEST"]


def fertilize() -> UnitOp:
    return ["FERTILIZE"]


def feed() -> UnitOp:
    return ["FEED"]


def care() -> UnitOp:
    return ["CARE"]


def collect_fertilizer() -> UnitOp:
    return ["COLLECT_FERTILIZER"]


def dig() -> UnitOp:
    return ["DIG"]


def build_coop() -> UnitOp:
    return ["BUILD_COOP"]


def build_pasture() -> UnitOp:
    return ["BUILD_PASTURE"]


def pickup(item: Item, n: int = 1) -> UnitOp:
    return ["PICKUP", item, n]


def drop() -> UnitOp:
    return ["DROP"]


def place(item: Item, n: int = 1) -> UnitOp:
    return ["PLACE", item, n]


# Market ops ---------------------------------------------------------------


def buy_seed(crop: Crop, n: int = 1) -> MarketOrder:
    return ["BUY_SEED", crop, n]


def buy_animal(animal: Animal, n: int = 1) -> MarketOrder:
    return ["BUY_ANIMAL", animal, n]


def buy_product(product: BuyableProduct, n: int = 1) -> MarketOrder:
    return ["BUY_PRODUCT", product, n]


def sell(product: Product, n: int = 1) -> MarketOrder:
    return ["SELL", product, n]


def hire() -> MarketOrder:
    return ["HIRE"]


def buy_land() -> MarketOrder:
    return ["BUY_LAND"]


def action(
    farmer: UnitOp | None = None,
    hands: list[UnitOp] | None = None,
    market: list[MarketOrder] | None = None,
) -> ActionDict:
    """Assemble the action dict returned by an agent for one turn."""
    return {
        "farmer": farmer if farmer is not None else ["PASS"],
        "hands": list(hands) if hands else [],
        "market": list(market) if market else [],
    }
