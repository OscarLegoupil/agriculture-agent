"""Generate the internal Elo ladder report for baselines vs built-in agents.

Runs a full round-robin (all pairs, seed-swapped) between the shipped
baselines and the built-in agents, computes Bradley-Terry ratings on the
Elo scale, and writes:

  - reports/baselines-elo.md   with a ranking table and win-rate matrix
  - reports/figures/baselines-elo.png       (bar chart)
  - reports/figures/baselines-matrix.png    (heatmap)

Invoke:
  uv run python -m kaggriculture.eval.baselines_report
"""

from __future__ import annotations

import argparse
import itertools
from pathlib import Path

from kaggriculture.eval import (
    bradley_terry_fit,
    bradley_terry_to_elo_scale,
    run_pairing,
    summarize,
)

_ROOT = Path(__file__).resolve().parents[3]
_BASELINES_DIR = _ROOT / "src" / "kaggriculture" / "agent" / "baselines"

_DEFAULT_AGENTS: list[tuple[str, str]] = [
    ("pass", "pass"),
    ("random", "random"),
    ("starter", "starter"),
    ("v0_wheat", str(_BASELINES_DIR / "v0_wheat.py")),
    ("v1_mixed", str(_BASELINES_DIR / "v1_mixed.py")),
    ("v2_animals", str(_BASELINES_DIR / "v2_animals.py")),
    ("v3_market", str(_BASELINES_DIR / "v3_market.py")),
    ("v4_expansion", str(_BASELINES_DIR / "v4_expansion.py")),
]


def _as_int(value: object) -> int:
    """Narrow an `object` stat value to `int` for arithmetic.

    Stats dicts store counts as ints under an `object` value type to keep the
    schema open. This helper asserts the narrowing so mypy is happy without
    scattering `# type: ignore` across the module.
    """
    assert isinstance(value, int), f"expected int, got {type(value).__name__}"
    return value


def _run_round_robin(
    agents: list[tuple[str, str]],
    seeds: list[int],
    workers: int | None,
    config: dict[str, int],
) -> dict[tuple[str, str], dict[str, object]]:
    """Return per-pair summary stats keyed by (short_a, short_b)."""
    stats: dict[tuple[str, str], dict[str, object]] = {}
    all_results = []
    for (short_a, path_a), (short_b, path_b) in itertools.combinations(agents, 2):
        results = run_pairing(
            path_a,
            path_b,
            seeds=seeds,
            workers=workers,
            swap_seats=True,
            config=config,
        )
        s = summarize(results)
        s["short_a"] = short_a
        s["short_b"] = short_b
        stats[(short_a, short_b)] = s
        all_results.extend(results)
    return stats


def _fit_ratings(
    agents: list[tuple[str, str]],
    stats: dict[tuple[str, str], dict[str, object]],
) -> dict[str, float]:
    from kaggriculture.eval.rating import Match

    matches: list[Match] = []
    path_to_short = {path: short for short, path in agents}
    for (short_a, short_b), s in stats.items():
        for _ in range(_as_int(s["wins_a"])):
            matches.append(Match(short_a, short_b, 1.0))
        for _ in range(_as_int(s["wins_b"])):
            matches.append(Match(short_a, short_b, 0.0))
        for _ in range(_as_int(s["ties"])):
            matches.append(Match(short_a, short_b, 0.5))
    _ = path_to_short
    strengths = bradley_terry_fit(matches)
    return bradley_terry_to_elo_scale(strengths)


def _render_report(
    agents: list[tuple[str, str]],
    stats: dict[tuple[str, str], dict[str, object]],
    elo: dict[str, float],
    seeds: list[int],
    out_md: Path,
    fig_elo: Path,
    fig_matrix: Path,
) -> None:
    import matplotlib.pyplot as plt
    import numpy as np

    shorts = [short for short, _ in agents]
    ordered = sorted(shorts, key=lambda a: -elo.get(a, 0.0))

    # Bar chart of Elo.
    fig, ax = plt.subplots(figsize=(9, 4.5))
    values = [elo[a] for a in ordered]
    ax.bar(ordered, values, color="#1f77b4")
    ax.axhline(1500, color="black", linestyle=":", linewidth=0.8, label="mean (1500)")
    ax.set_ylabel("Bradley-Terry Elo")
    ax.set_title("Baseline ladder (round-robin, seed-swapped)")
    for i, v in enumerate(values):
        ax.text(i, v + 10, f"{v:.0f}", ha="center", fontsize=9)
    ax.grid(True, axis="y", alpha=0.3)
    fig.tight_layout()
    fig_elo.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(fig_elo, dpi=140, bbox_inches="tight")
    plt.close(fig)

    # Win-rate matrix (row wins vs column).
    n = len(shorts)
    matrix = np.full((n, n), np.nan)
    for i, row in enumerate(shorts):
        for j, col in enumerate(shorts):
            if i == j:
                continue
            key = (row, col) if (row, col) in stats else (col, row)
            s = stats[key]
            wins = _as_int(s["wins_a" if key == (row, col) else "wins_b"])
            total = _as_int(s["n"])
            matrix[i, j] = wins / total if total else 0.0

    fig2, ax2 = plt.subplots(figsize=(7, 6))
    im = ax2.imshow(matrix, cmap="RdBu_r", vmin=0.0, vmax=1.0)
    ax2.set_xticks(range(n), labels=shorts, rotation=45, ha="right")
    ax2.set_yticks(range(n), labels=shorts)
    ax2.set_xlabel("opponent")
    ax2.set_ylabel("agent")
    ax2.set_title("Row's win rate vs column (round-robin)")
    for i in range(n):
        for j in range(n):
            if i == j or np.isnan(matrix[i, j]):
                continue
            ax2.text(j, i, f"{matrix[i, j]:.0%}", ha="center", va="center", fontsize=8)
    fig2.colorbar(im, ax=ax2, fraction=0.046, pad=0.04)
    fig2.tight_layout()
    fig2.savefig(fig_matrix, dpi=140, bbox_inches="tight")
    plt.close(fig2)

    # Markdown report.
    lines = [
        "# Baseline Elo ladder",
        "",
        f"Round-robin over {len(agents)} agents (built-ins plus v0-v4), "
        f"{len(seeds)} seeds x 2 seat assignments per pair. "
        "Ratings are Bradley-Terry MLE re-scaled to the Elo convention (mean 1500, "
        "400 per decade of log-odds).",
        "",
        "![Elo ratings](figures/baselines-elo.png)",
        "",
        "## Ranking",
        "",
        "| Agent | Elo |",
        "|-------|-----|",
    ]
    for a in ordered:
        lines.append(f"| `{a}` | {elo[a]:.0f} |")
    lines += [
        "",
        "## Win-rate matrix",
        "",
        "Row's win rate against column, ties excluded from the numerator.",
        "",
        "![Win rate matrix](figures/baselines-matrix.png)",
        "",
        "## Notes",
        "",
        "- Baseline commits each closed with a two-agent A/B (v_n vs v_{n-1}); "
        "this report is the aggregate view.",
        f"- Seeds used: {seeds[0]}-{seeds[-1]}.",
        "- Every episode is reproducible from `(agent_pair, seed, seat_0)` plus "
        "the `kaggle-environments` version pinned in `pyproject.toml`.",
        "",
    ]
    out_md.parent.mkdir(parents=True, exist_ok=True)
    out_md.write_text("\n".join(lines), encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="kagg-baselines-report")
    ap.add_argument("--seeds-n", type=int, default=5)
    ap.add_argument("--seed-start", type=int, default=0)
    ap.add_argument("--episode-steps", type=int, default=720)
    ap.add_argument("--workers", type=int, default=None)
    ap.add_argument("--reports-dir", type=Path, default=_ROOT / "reports")
    ap.add_argument("--figures-dir", type=Path, default=_ROOT / "reports" / "figures")
    args = ap.parse_args(argv)

    seeds = list(range(args.seed_start, args.seed_start + args.seeds_n))
    config = {"episodeSteps": args.episode_steps}

    print(f"Running round-robin over {len(_DEFAULT_AGENTS)} agents, {len(seeds)} seeds each.")
    stats = _run_round_robin(_DEFAULT_AGENTS, seeds, args.workers, config)
    elo = _fit_ratings(_DEFAULT_AGENTS, stats)

    out_md = args.reports_dir / "baselines-elo.md"
    fig_elo = args.figures_dir / "baselines-elo.png"
    fig_matrix = args.figures_dir / "baselines-matrix.png"
    _render_report(_DEFAULT_AGENTS, stats, elo, seeds, out_md, fig_elo, fig_matrix)
    print(f"Wrote {out_md} + {fig_elo} + {fig_matrix}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
