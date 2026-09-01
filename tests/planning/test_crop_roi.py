"""Tests for `kaggriculture.planning.crop_roi`."""

from __future__ import annotations

import math

import pytest

from kaggriculture.env.constants import CROPS, MARKET_PARAMS
from kaggriculture.planning.crop_roi import (
    CropRoi,
    crop_roi,
    crop_roi_table,
    lifecycle_units_and_days,
    one_time_yield_trace,
    ongoing_cumulative_trace,
)


def test_one_time_wheat_watered_reaches_four_at_day_four() -> None:
    trace = one_time_yield_trace("WHEAT", 6, watered=True, fertilized=False)
    # window is [2, 4], so yield goes 1,1,2,3,4,4,... and starts decaying past day 5.
    assert trace[:5] == [1, 1, 2, 3, 4]


def test_one_time_wheat_fertilized_caps_at_six() -> None:
    trace = one_time_yield_trace("WHEAT", 4, watered=True, fertilized=True)
    # +2 per day inside the window from y=1: 1,1,3,5,6 (capped at max_yield=6).
    assert trace == [1, 1, 3, 5, 6]


def test_one_time_wheat_unwatered_stays_at_one() -> None:
    trace = one_time_yield_trace("WHEAT", 4, watered=False)
    assert set(trace) == {1}


def test_one_time_wheat_decays_after_peak() -> None:
    trace = one_time_yield_trace("WHEAT", 12, watered=True, fertilized=False)
    # peak 4 on day 4; decay fires on days 7, 9, 11 (`(day - max_day - 1) % 2 == 0`).
    assert trace[4] == 4
    assert trace[7] == 3
    assert trace[9] == 2


def test_ongoing_tomato_watered_hits_four_units() -> None:
    trace = ongoing_cumulative_trace("TOMATO", 12, watered=True, fertilized=False)
    # productions on days 8, 9, 10, 11.
    assert trace[7] == 0
    assert trace[8] == 1
    assert trace[11] == 4
    assert trace[12] == 4


def test_ongoing_tomato_fertilized_doubles_output() -> None:
    trace = ongoing_cumulative_trace("TOMATO", 11, watered=True, fertilized=True)
    assert trace[-1] == 8


def test_ongoing_unwatered_produces_nothing() -> None:
    trace = ongoing_cumulative_trace("STRAWBERRY", 20, watered=False)
    assert trace[-1] == 0


def test_one_time_helper_rejects_ongoing_crop() -> None:
    with pytest.raises(ValueError):
        one_time_yield_trace("TOMATO", 10)


def test_ongoing_helper_rejects_one_time_crop() -> None:
    with pytest.raises(ValueError):
        ongoing_cumulative_trace("WHEAT", 10)


def test_lifecycle_units_days_wheat_watered() -> None:
    units, days = lifecycle_units_and_days("WHEAT", watered=True, fertilized=False)
    assert (units, days) == (4, 4)


def test_lifecycle_units_days_wheat_fertilized() -> None:
    units, days = lifecycle_units_and_days("WHEAT", watered=True, fertilized=True)
    assert (units, days) == (6, 4)


def test_lifecycle_units_days_strawberry() -> None:
    units, days = lifecycle_units_and_days("STRAWBERRY", watered=True, fertilized=False)
    # first_yield_day=10, interval=2, max_yield=4 -> last prod on day 16.
    assert (units, days) == (4, 16)


def test_crop_roi_wheat_watered_matches_notebook() -> None:
    roi = crop_roi("WHEAT", watered=True, fertilized=False)
    assert roi.gross_revenue == 4 * 25
    assert roi.net_revenue == 4 * 25 - 10
    assert roi.coins_per_tile_per_day == pytest.approx(22.5)


def test_crop_roi_wheat_fertilized_matches_notebook() -> None:
    roi = crop_roi("WHEAT", watered=True, fertilized=True)
    assert roi.lifecycle_units == 6
    assert roi.coins_per_tile_per_day == pytest.approx(35.0)


def test_crop_roi_strawberry_fertilized_matches_notebook() -> None:
    roi = crop_roi("STRAWBERRY", watered=True, fertilized=True)
    assert roi.lifecycle_units == 8
    assert roi.coins_per_tile_per_day == pytest.approx((8 * 120 - 100) / 16)


def test_crop_roi_accepts_price_override() -> None:
    roi = crop_roi("MELON", watered=True, fertilized=False, price=1.0)
    # premium collapses on glut: at $1 the net turns negative on a lifecycle basis.
    assert roi.net_revenue == 6 * 1.0 - CROPS["MELON"]["seed"]
    assert roi.price == 1.0


def test_crop_roi_deducts_fertilizer_cost() -> None:
    fert_price = float(MARKET_PARAMS["FERTILIZER"]["base"])
    plain = crop_roi("WHEAT", watered=True, fertilized=True)
    with_fert_cost = crop_roi("WHEAT", watered=True, fertilized=True, fertilizer_cost=fert_price)
    assert math.isclose(with_fert_cost.net_revenue, plain.net_revenue - fert_price)


def test_crop_roi_rejects_fertilizer_cost_when_not_fertilized() -> None:
    with pytest.raises(ValueError):
        crop_roi("WHEAT", fertilized=False, fertilizer_cost=100.0)


def test_crop_roi_rejects_unknown_crop() -> None:
    with pytest.raises(KeyError):
        crop_roi("BANANA")


def test_crop_roi_table_covers_all_crops() -> None:
    table = crop_roi_table(watered=True, fertilized=False)
    assert {row.crop for row in table} == set(CROPS)
    assert all(isinstance(row, CropRoi) for row in table)


def test_crop_roi_table_price_map_overrides() -> None:
    prices = {"WHEAT": 100.0}
    table = crop_roi_table(watered=True, fertilized=False, price_map=prices)
    wheat = next(row for row in table if row.crop == "WHEAT")
    carrot = next(row for row in table if row.crop == "CARROT")
    assert wheat.price == 100.0
    assert carrot.price == float(MARKET_PARAMS["CARROT"]["base"])
