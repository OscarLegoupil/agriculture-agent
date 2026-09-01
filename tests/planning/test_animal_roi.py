"""Tests for `kaggriculture.planning.animal_roi`."""

from __future__ import annotations

import pytest

from kaggriculture.env.constants import ANIMALS, MARKET_PARAMS
from kaggriculture.planning.animal_roi import (
    AnimalRoi,
    animal_roi,
    animal_roi_table,
    cumulative_net_trace,
)


def test_cumulative_trace_starts_at_negative_buy_cost() -> None:
    trace = cumulative_net_trace("GOOSE", 0)
    assert trace == [-300.0]


def test_cumulative_trace_goose_reaches_first_yield_day() -> None:
    trace = cumulative_net_trace("GOOSE", 4)
    # day 0: -300; days 1-3: -25 each; day 4: +50 production then -25 feed.
    assert trace == [-300.0, -325.0, -350.0, -375.0, -350.0]


def test_cumulative_trace_cared_goose_doubles_steady_yield() -> None:
    uncared = cumulative_net_trace("GOOSE", 10, cared=False)
    cared = cumulative_net_trace("GOOSE", 10, cared=True)
    # cared goose gets +interval = +1 extra unit per production in steady state.
    # after enough days, cared curve is above uncared by (day - first_yield_day + 1) * price.
    assert cared[-1] > uncared[-1]


def test_cumulative_trace_respects_feed_price() -> None:
    cheap = cumulative_net_trace("GOOSE", 20, feed_cost_per_day=0.0)
    expensive = cumulative_net_trace("GOOSE", 20, feed_cost_per_day=100.0)
    assert cheap[-1] > expensive[-1]


def test_cumulative_trace_rejects_unknown_animal() -> None:
    with pytest.raises(KeyError):
        cumulative_net_trace("DRAGON", 5)


def test_animal_roi_goose_steady_state_matches_notebook() -> None:
    roi = animal_roi("GOOSE")
    assert roi.steady_units_per_day == pytest.approx(1.0)
    assert roi.gross_per_day == pytest.approx(50.0)
    assert roi.net_per_day == pytest.approx(25.0)


def test_animal_roi_cow_steady_state_matches_notebook() -> None:
    roi = animal_roi("COW")
    assert roi.steady_units_per_day == pytest.approx(0.5)
    assert roi.gross_per_day == pytest.approx(80.0)
    assert roi.net_per_day == pytest.approx(55.0)


def test_animal_roi_sheep_steady_state_matches_notebook() -> None:
    roi = animal_roi("SHEEP")
    assert roi.steady_units_per_day == pytest.approx(1.0 / 3.0)
    assert roi.gross_per_day == pytest.approx(200.0 / 3.0)
    assert roi.net_per_day == pytest.approx(200.0 / 3.0 - 25.0)


def test_animal_roi_cared_adds_one_unit_per_day_at_steady_state() -> None:
    for animal in ANIMALS:
        base = animal_roi(animal, cared=False)
        cared = animal_roi(animal, cared=True)
        assert cared.steady_units_per_day == pytest.approx(base.steady_units_per_day + 1.0)


def test_animal_roi_breakeven_uses_discrete_trace() -> None:
    # Goose: exact discrete break-even at day 18 (see notebook 03 walkthrough).
    roi = animal_roi("GOOSE")
    assert roi.days_to_breakeven == pytest.approx(18.0)


def test_animal_roi_breakeven_none_when_net_negative() -> None:
    roi = animal_roi("GOOSE", feed_cost_per_day=100.0)
    assert roi.net_per_day < 0
    assert roi.days_to_breakeven is None


def test_animal_roi_accepts_price_override() -> None:
    roi = animal_roi("SHEEP", product_price=1.0)
    assert roi.product_price == 1.0
    assert roi.gross_per_day == pytest.approx(1.0 / 3.0)


def test_animal_roi_rejects_unknown_animal() -> None:
    with pytest.raises(KeyError):
        animal_roi("DRAGON")


def test_animal_roi_table_covers_all_animals() -> None:
    rows = animal_roi_table()
    assert {row.animal for row in rows} == set(ANIMALS)
    assert all(isinstance(row, AnimalRoi) for row in rows)


def test_animal_roi_table_price_map_overrides() -> None:
    rows = animal_roi_table(price_map={"MILK": 1.0})
    cow = next(row for row in rows if row.animal == "COW")
    goose = next(row for row in rows if row.animal == "GOOSE")
    assert cow.product_price == 1.0
    assert goose.product_price == float(MARKET_PARAMS["EGG"]["base"])
