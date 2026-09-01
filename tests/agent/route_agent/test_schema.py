"""Schema construction and immutability sanity checks."""

from __future__ import annotations

import pytest

from kaggriculture.agent.route_agent import (
    CropAssignment,
    FeedStockpile,
    HireSchedule,
    LandBuy,
    MarketPolicy,
    Route,
    RouteOverride,
    StructureAssignment,
)
from kaggriculture.agent.route_agent.schema import HandAssignment


def _minimal_market_policy() -> MarketPolicy:
    return MarketPolicy(
        seed_buy_order=("WHEAT",),
        animal_buy_order=(),
        hire=None,
        feed_stockpiles=(),
        sell_order=("WHEAT",),
        sell_min_price={"WHEAT": 25},
        liquidate_from_day=29,
        shed_high_water=80,
    )


def test_route_is_immutable() -> None:
    r = Route(
        name="t",
        description="",
        crops=(CropAssignment(tile=(3, 4), crop="WHEAT"),),
        structures=(),
        hand=HandAssignment(primary_tiles=(), fallback_tiles=()),
        land_buys=(),
        market_policy=_minimal_market_policy(),
        overrides=(),
    )
    with pytest.raises(AttributeError):
        r.name = "u"  # type: ignore[misc]


def test_all_schema_types_construct() -> None:
    crop = CropAssignment(tile=(0, 0), crop="WHEAT")
    struct = StructureAssignment(tile=(1, 1), kind="COOP", animal="GOOSE")
    hire = HireSchedule(from_day=3, per_day=1, price_cap=10)
    land = LandBuy(quadrant="NE", money_buffer=1400, from_day=5)
    feed = FeedStockpile(product="WHEAT", for_animal="GOOSE", buy_below=20, cap=10, reserve=2)
    override = RouteOverride(turn=0, unit="farmer", action=["PASS"])
    hand = HandAssignment(primary_tiles=((0, 0),), fallback_tiles=())
    mp = MarketPolicy(
        seed_buy_order=("WHEAT",),
        animal_buy_order=("GOOSE",),
        hire=hire,
        feed_stockpiles=(feed,),
        sell_order=("WHEAT",),
        sell_min_price={"WHEAT": 25},
        liquidate_from_day=29,
        shed_high_water=80,
    )
    route = Route(
        name="all",
        description="",
        crops=(crop,),
        structures=(struct,),
        hand=hand,
        land_buys=(land,),
        market_policy=mp,
        overrides=(override,),
    )
    assert route.crops[0].crop == "WHEAT"
    assert route.structures[0].animal == "GOOSE"
    assert route.market_policy.hire is not None
