"""Beam-search unit tests using cheap synthetic scoring functions."""

from __future__ import annotations

from kaggriculture.search.beam import (
    GridSpec,
    beam_search,
    dict_neighbours,
    dict_to_tuple,
    tuple_to_dict,
)


def test_beam_search_finds_grid_maximum() -> None:
    grids = {"x": GridSpec("x", (0, 1, 2, 3, 4)), "y": GridSpec("y", (0, 1, 2))}

    def target(state: tuple[tuple[str, float | int], ...]) -> float:
        s = tuple_to_dict(state)
        # Peak at (3, 2).
        return -((s["x"] - 3) ** 2 + (s["y"] - 2) ** 2)

    def nbs(state: tuple[tuple[str, float | int], ...]):
        s = tuple_to_dict(state)
        return [dict_to_tuple(n) for n in dict_neighbours(s, grids)]

    initial = [dict_to_tuple({"x": 0, "y": 0})]
    best, trace = beam_search(initial, nbs, target, beam_width=2, max_iterations=10)
    assert tuple_to_dict(best) == {"x": 3, "y": 2}
    assert len(trace) >= 1


def test_beam_search_dedupes_states() -> None:
    grids = {"x": GridSpec("x", (0, 1, 2))}

    def target(state):
        return dict(state)["x"]

    def nbs(state):
        s = tuple_to_dict(state)
        return [dict_to_tuple(n) for n in dict_neighbours(s, grids)]

    calls: list[tuple[tuple[str, float | int], ...]] = []

    def counting_target(state):
        calls.append(state)
        return target(state)

    initial = [dict_to_tuple({"x": 0})]
    beam_search(initial, nbs, counting_target, beam_width=1, max_iterations=5)
    assert len(set(calls)) == len(calls) == 3


def test_grid_spec_edge_neighbours() -> None:
    g = GridSpec("k", (10, 20, 30))
    assert g.neighbours(10) == [20]
    assert g.neighbours(20) == [10, 30]
    assert g.neighbours(30) == [20]
    assert g.neighbours(999) == []
