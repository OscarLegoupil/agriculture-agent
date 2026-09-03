"""Small beam-search implementation over a discrete parameter grid.

Each state is a hashable tuple representation of a configuration; the
neighbours function generates all one-step moves in the grid, evaluate
scores each state, and the top-``beam_width`` are carried forward.
"""

from __future__ import annotations

from collections.abc import Callable, Hashable, Iterable
from dataclasses import dataclass, field


@dataclass
class BeamStep:
    iteration: int
    state: Hashable
    score: float
    n_evaluations: int


def beam_search(
    initial: Iterable[Hashable],
    neighbours: Callable[[Hashable], Iterable[Hashable]],
    evaluate: Callable[[Hashable], float],
    *,
    beam_width: int = 3,
    max_iterations: int = 3,
    on_step: Callable[[BeamStep], None] | None = None,
) -> tuple[Hashable, list[BeamStep]]:
    """Return the best state and a trace of every evaluated candidate.

    - ``initial``: seed states (usually one baseline).
    - ``neighbours(state)``: generator of adjacent states to try.
    - ``evaluate(state)``: score to maximise (higher is better).
    - ``beam_width``: how many top states carry forward each iteration.
    - ``max_iterations``: hard cap on iterations. The loop also stops
      early once no neighbour improves on the current best.
    """
    if beam_width < 1:
        raise ValueError(f"beam_width must be >= 1, got {beam_width}")
    if max_iterations < 1:
        raise ValueError(f"max_iterations must be >= 1, got {max_iterations}")

    trace: list[BeamStep] = []
    seen: dict[Hashable, float] = {}

    def _score(state: Hashable, iteration: int) -> float:
        if state in seen:
            return seen[state]
        s = float(evaluate(state))
        seen[state] = s
        step = BeamStep(iteration=iteration, state=state, score=s, n_evaluations=len(seen))
        trace.append(step)
        if on_step is not None:
            on_step(step)
        return s

    beam: list[tuple[Hashable, float]] = []
    for s in initial:
        beam.append((s, _score(s, 0)))
    beam.sort(key=lambda x: x[1], reverse=True)
    beam = beam[:beam_width]

    for it in range(1, max_iterations + 1):
        candidates: dict[Hashable, float] = {s: sc for s, sc in beam}
        expanded = False
        for state, _ in list(beam):
            for nb in neighbours(state):
                if nb in candidates:
                    continue
                candidates[nb] = _score(nb, it)
                expanded = True
        if not expanded:
            break
        beam = sorted(candidates.items(), key=lambda x: x[1], reverse=True)[:beam_width]

    best_state, _ = beam[0]
    return best_state, trace


@dataclass
class GridSpec:
    """Discrete grid over one parameter, exposed as a sequence for neighbour
    generation. Values must be ordered ascending for the neighbour walk.
    """

    name: str
    values: tuple[float | int, ...] = field()

    def index(self, value: float | int) -> int:
        return self.values.index(value)

    def neighbours(self, value: float | int) -> list[float | int]:
        try:
            i = self.index(value)
        except ValueError:
            return []
        out: list[float | int] = []
        if i > 0:
            out.append(self.values[i - 1])
        if i < len(self.values) - 1:
            out.append(self.values[i + 1])
        return out


def dict_neighbours(
    state: dict[str, float | int], grids: dict[str, GridSpec]
) -> Iterable[dict[str, float | int]]:
    """Yield one-parameter-changed neighbours of a state dict."""
    for key, grid in grids.items():
        for v in grid.neighbours(state[key]):
            nb = dict(state)
            nb[key] = v
            yield nb


def dict_to_tuple(state: dict[str, float | int]) -> tuple[tuple[str, float | int], ...]:
    """Freeze a dict state for use as a hashable beam key."""
    return tuple(sorted(state.items()))


def tuple_to_dict(state: tuple[tuple[str, float | int], ...]) -> dict[str, float | int]:
    return dict(state)
