"""Tests for allocator-driven route generation."""

from __future__ import annotations

from collections import Counter
from pathlib import Path

import pytest

from kaggriculture.agent.route_agent.generate import (
    best_fill_crop,
    candidate_routes,
    expected_volumes,
    generate_route,
    plan_revenue,
    quadrant_tiles,
    tiles_by_shed_distance,
)
from kaggriculture.agent.route_agent.loader import load_route, route_to_dict, write_route
from kaggriculture.agent.route_agent.schema import Route
from kaggriculture.market.forecaster import average_sale_price
from kaggriculture.planning.phased_allocator import build_phased_plan

_RAMP = {0: 4, 2: 7, 5: 9}


@pytest.fixture(scope="module")
def route() -> Route:
    """The default generated route. The ceiling sweep is slow, so share one."""
    return generate_route(name="gen", hire_ramp=_RAMP)


def test_quadrant_tiles_cover_the_board_exactly_once() -> None:
    tiles = [t for q in ("NW", "NE", "SW", "SE") for t in quadrant_tiles(q)]
    assert len(tiles) == 100
    assert len(set(tiles)) == 100


def test_tiles_are_ordered_outwards_from_the_shed() -> None:
    order = tiles_by_shed_distance(["NW"])
    assert len(order) == 25
    assert order[0] == (4, 4)  # the NW shed-access tile
    assert order[-1] == (0, 0)  # the far corner


def test_best_fill_crop_respects_the_days_left() -> None:
    assert best_fill_crop(remaining_days=30) == "MELON"
    # A melon needs ten days to ripen, a carrot three.
    assert best_fill_crop(remaining_days=8) == "CARROT"
    assert best_fill_crop(remaining_days=2) is None


def test_expected_volumes_counts_one_fertilizer_per_animal_per_day() -> None:
    plan = build_phased_plan(
        season_days=30, max_animals_per_species={"GOOSE": 2, "COW": 0, "SHEEP": 0}
    )
    volumes = expected_volumes(plan)
    head = plan.phases[0].allocation.animal_counts.get("GOOSE", 0)
    assert head > 0
    assert volumes["FERTILIZER"] == head * 30


def test_plan_revenue_prices_volume_not_base() -> None:
    plan = build_phased_plan(season_days=30)
    volumes = expected_volumes(plan)
    assert volumes.get("MELON", 0) > 100
    # Selling that many melons averages well under the 250 base price.
    assert average_sale_price("MELON", volumes["MELON"]) < 250
    assert plan_revenue(plan) > 0


def test_generated_route_is_phased_and_loadable(route: Route, tmp_path: Path) -> None:
    assert route.phases
    assert route.crops == ()  # a phased route carries its tiles in the phases
    path = write_route(route, tmp_path / "gen.yaml")
    assert load_route(path) == route


def test_generated_route_never_double_books_a_tile(route: Route) -> None:
    for phase in route.phases:
        tiles = [c.tile for c in phase.crops] + [s.tile for s in phase.structures]
        assert len(tiles) == len(set(tiles))


def test_a_tile_keeps_its_job_across_phases(route: Route) -> None:
    jobs: dict[tuple[int, int], str] = {}
    for phase in route.phases:
        for s in phase.structures:
            assert jobs.setdefault(s.tile, "structure") == "structure"
        for c in phase.crops:
            assert jobs.setdefault(c.tile, "crop") == "crop"


def test_generated_route_fits_the_unlocked_quadrant(route: Route) -> None:
    for phase in route.phases:
        for tile in [c.tile for c in phase.crops] + [s.tile for s in phase.structures]:
            assert 0 <= tile[0] < 5 and 0 <= tile[1] < 5


def test_tail_phase_switches_to_a_crop_that_still_ripens(route: Route) -> None:
    tail = route.phases[-1]
    assert tail.from_day >= 15
    for c in tail.crops:
        assert c.crop != "MELON"


def test_structures_sit_closer_to_the_shed_than_the_crops(route: Route) -> None:
    final = route.phases[-1]
    order = tiles_by_shed_distance(["NW"])
    worst_structure = max(order.index(s.tile) for s in final.structures)
    best_crop = min(order.index(c.tile) for c in final.crops)
    assert worst_structure < best_crop


def test_candidate_routes_are_distinct_shapes_and_ranked() -> None:
    routes = candidate_routes(name="gen", hire_ramp=_RAMP, top_k=5)
    assert len(routes) == 5
    shapes = {_shape(r) for r in routes}
    assert len(shapes) == len(routes)


def test_explicit_caps_bypass_the_ceiling_sweep() -> None:
    route = generate_route(
        name="gen", hire_ramp=_RAMP, max_animals_per_species={"GOOSE": 0, "COW": 0, "SHEEP": 0}
    )
    assert all(not phase.structures for phase in route.phases)


def test_generated_route_serializes_to_yaml_and_back(route: Route, tmp_path: Path) -> None:
    path = write_route(route, tmp_path / "r.yaml")
    assert load_route(path) == route
    assert route_to_dict(load_route(path)) == route_to_dict(route)


@pytest.mark.parametrize("season_days", [10, 20, 30])
def test_generation_holds_up_across_season_lengths(season_days: int) -> None:
    route = generate_route(name="gen", season_days=season_days, hire_ramp=_RAMP)
    assert route.phases
    assert all(p.from_day < season_days for p in route.phases)


def _shape(route: Route) -> tuple[tuple[str, int], ...]:
    final = route.phases[-1]
    counts = Counter(s.animal for s in final.structures) + Counter(c.crop for c in final.crops)
    return tuple(sorted(counts.items()))
