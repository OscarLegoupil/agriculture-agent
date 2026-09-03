"""Configuration evaluator used by the beam search.

Given a parameter dict and a challenger opponent, run a small paired-seed
A/B and return a win-rate-based score. The score is
``2 * win_rate - 1`` in [-1, 1] so higher-is-better, and ties count as
zero.

Evaluations are deterministic given ``seeds`` and ``opponent`` so the
same state is not re-scored during a beam iteration.
"""

from __future__ import annotations

import shutil
import tempfile
import textwrap
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from kaggriculture.eval.runner import run_pairing, summarize


@dataclass(frozen=True, slots=True)
class EvalResult:
    n: int
    wins_a: int
    wins_b: int
    ties: int
    mean_gap: float

    @property
    def score(self) -> float:
        if self.n == 0:
            return 0.0
        return (self.wins_a - self.wins_b) / self.n


_AGENT_TEMPLATE = textwrap.dedent(
    """\
    from __future__ import annotations
    from typing import Any
    import yaml
    from kaggriculture.agent.route_agent.loader import route_from_dict
    from kaggriculture.agent.route_agent.micro import wrap_with_micro
    from kaggriculture.agent.route_agent.runner import RouteAgent

    _YAML = {yaml_literal!r}

    _route = route_from_dict(yaml.safe_load(_YAML))
    _ra = RouteAgent(_route)


    def _base(obs):
        return _ra(obs)


    _agent = wrap_with_micro(
        _base,
        sell_thresholds=dict(_route.market_policy.sell_min_price),
        {micro_kwargs},
    )


    def agent(obs: dict[str, Any]) -> dict[str, Any]:
        return _agent(obs)
    """
)


def _format_kwargs(kwargs: dict[str, Any]) -> str:
    return ",\n        ".join(f"{k}={v!r}" for k, v in sorted(kwargs.items()))


def build_agent_file(yaml_text: str, micro_kwargs: dict[str, Any], out_path: Path) -> Path:
    """Write a self-contained agent .py file that env.run can load."""
    src = _AGENT_TEMPLATE.format(
        yaml_literal=yaml_text,
        micro_kwargs=_format_kwargs(micro_kwargs),
    )
    out_path.write_text(src, encoding="utf-8")
    return out_path


def evaluate_config(
    yaml_text: str,
    micro_kwargs: dict[str, Any],
    opponent_agent_path: str,
    seeds: Sequence[int],
    *,
    workers: int = 4,
) -> EvalResult:
    """Run a paired A/B and return a signed score.

    Writes a temporary agent file so the process pool workers can load it
    via ``env.run(path)``. The file is deleted after the pairing runs.
    """
    tmpdir = Path(tempfile.mkdtemp(prefix="kagg_search_"))
    try:
        agent_path = build_agent_file(
            yaml_text=yaml_text,
            micro_kwargs=micro_kwargs,
            out_path=tmpdir / "agent.py",
        )
        results = run_pairing(
            str(agent_path),
            opponent_agent_path,
            seeds=list(seeds),
            swap_seats=True,
            workers=workers,
            config={"episodeSteps": 720},
        )
        s = summarize(results)
        return EvalResult(
            n=int(s["n"]),
            wins_a=int(s["wins_a"]),
            wins_b=int(s["wins_b"]),
            ties=int(s["ties"]),
            mean_gap=float(s["mean_coin_gap_a_minus_b"]),
        )
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)
