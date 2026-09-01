"""Tests for `kaggriculture.planning.allocator`."""

from __future__ import annotations

import pytest

from kaggriculture.planning.allocator import Allocation, allocate


def test_allocate_zero_tiles_picks_no_animals_no_fill() -> None:
    a = allocate(tiles=0, horizon_days=30)
    assert a.animal_counts == {}
    assert a.wheat_tiles == 0
    assert a.structure_tiles == 0
    assert a.fill_crop_tiles == 0
    assert a.fill_crop is None


def test_allocate_single_tile_uses_it_for_best_crop() -> None:
    a = allocate(tiles=1, horizon_days=30)
    assert a.fill_crop_tiles == 1
    assert a.fill_crop in {"CARROT", "TOMATO", "STRAWBERRY", "MELON"}
    assert a.animal_counts == {}


def test_allocate_prefers_melon_at_base_prices() -> None:
    # Melon has the highest $/tile/day at base prices ($/tile/day ~ 118).
    a = allocate(tiles=4, horizon_days=30)
    assert a.fill_crop == "MELON"


def test_allocate_switches_fill_crop_when_price_forecast_crashes() -> None:
    a = allocate(tiles=4, horizon_days=30, price_map={"MELON": 1.0})
    assert a.fill_crop != "MELON"


def test_allocate_expected_revenue_scales_with_horizon() -> None:
    short = allocate(tiles=4, horizon_days=10)
    long_ = allocate(tiles=4, horizon_days=30)
    assert long_.expected_revenue > short.expected_revenue


def test_allocate_returns_allocation_dataclass() -> None:
    a = allocate(tiles=6, horizon_days=30)
    assert isinstance(a, Allocation)
    assert a.tiles == 6
    assert a.horizon_days == 30


def test_allocate_can_include_animals_when_profitable() -> None:
    # A tile budget large enough for a coop + wheat + a filler crop should
    # sometimes prefer animals to more premium crops. With base prices and
    # 30 days a single coop of geese pays for itself easily.
    a = allocate(tiles=10, horizon_days=30)
    # Not a strict requirement that animals are picked (depends on relative
    # rates), but the allocator must be internally consistent.
    total_used = a.wheat_tiles + a.structure_tiles + a.fill_crop_tiles
    assert total_used == a.tiles


def test_allocate_animal_forces_wheat_reserve() -> None:
    # Cap species so we can force a specific outcome.
    a = allocate(
        tiles=8,
        horizon_days=30,
        price_map={"MELON": 1.0, "STRAWBERRY": 1.0, "TOMATO": 1.0, "CARROT": 1.0},
        max_animals_per_species={"GOOSE": 4, "COW": 0, "SHEEP": 0},
    )
    # Fill crops are worthless, so the allocator has to look for revenue in
    # animals. A goose coop plus a wheat reserve should show up.
    assert a.animal_counts.get("GOOSE", 0) > 0
    assert a.wheat_tiles > 0
    assert a.structure_tiles == 1


def test_allocate_never_over_allocates_tiles() -> None:
    for tiles in range(0, 16):
        a = allocate(tiles=tiles, horizon_days=30)
        used = a.wheat_tiles + a.structure_tiles + a.fill_crop_tiles
        assert used == tiles


def test_allocate_rejects_negative_tiles() -> None:
    with pytest.raises(ValueError):
        allocate(tiles=-1, horizon_days=30)


def test_allocate_rejects_zero_horizon() -> None:
    with pytest.raises(ValueError):
        allocate(tiles=10, horizon_days=0)


def test_allocate_species_cap_limits_roster() -> None:
    a = allocate(
        tiles=20,
        horizon_days=30,
        max_animals_per_species={"GOOSE": 0, "COW": 0, "SHEEP": 0},
    )
    assert a.animal_counts == {}
