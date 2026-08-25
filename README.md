# kaggriculture

Applied autonomous-agent work on the [Kaggriculture](https://www.kaggle.com/competitions/kaggriculture) simulation competition. Two agents compete on separate farms across a 30-day, 720-turn season on a dynamic market. The deliverable is a Python `agent(obs)` function submitted to Kaggle. This repository is a working project, not a submission notebook. It exists to demonstrate a reproducible, engineering-grade workflow from environment analysis to a competitive agent.

## Status

Milestone 1 (foundations, CI, deps, smoke test) and Milestone 2 (env wrappers, action legality, dynamics notebooks) are complete. Next: milestone 3, the evaluation harness. See open issues and milestones for the current plan.

## Quickstart

Prerequisites: Python 3.11 to 3.12, [uv](https://docs.astral.sh/uv/), Git, and a Kaggle account with API credentials configured (`~/.kaggle/kaggle.json`).

```bash
git clone https://github.com/OscarLegoupil/agriculture-agent.git
cd agriculture-agent
uv sync --extra dev --extra notebooks
uv run pytest
```

Run a full 720-turn episode locally:

```bash
make sim
```

## Repository layout

```
.
├── configs/               experiment configs (YAML)
├── data/                  generated replays and metrics (gitignored, DVC-tracked)
├── notebooks/             numbered environment analysis and evaluation notebooks
├── reports/               figures, model cards, writeups
├── src/kaggriculture/     installable package (agent, env, eval, planning, market)
└── tests/                 pytest suite
```

## Approach

The project is organized as a sequence of milestones, each tracked by GitHub issues:

1. Foundations and tooling
2. Environment wrapper and dynamics analysis
3. Evaluation harness (parallel episode runner, ELO rating, A/B testing)
4. Rule-based baselines
5. Economic planning core (per-tile ROI, allocation, feed budgeting)
6. Market and opponent modeling
7. Advanced planner (search or MCTS macro-planner plus micro-controller)
8. Submission, hardening, and final writeup

Each agent iteration is tracked as an issue stating a hypothesis, closed with a comment reporting Elo change, headline metrics, and a replay link.

## Environment analysis

Five numbered notebooks under [`notebooks/`](notebooks/) explore the simulator's dynamics. Figures are committed under [`reports/figures/`](reports/figures/).

1. [`01-market-curves.ipynb`](notebooks/01-market-curves.ipynb): sell-price curves for all 9 resources.
2. [`02-crop-yields.ipynb`](notebooks/02-crop-yields.ipynb): per-crop yield trajectories and a $/tile/day ROI table at base prices.
3. [`03-animal-economics.ipynb`](notebooks/03-animal-economics.ipynb): cumulative net revenue and break-even days per animal under two feed-cost regimes.
4. [`04-town-demand.ipynb`](notebooks/04-town-demand.ipynb): per-resource demand distribution across 5000 simulated seasons.
5. [`05-hire-cost.ipynb`](notebooks/05-hire-cost.ipynb): Fibonacci hire cost and break-even by resource.

The env wrapper package [`src/kaggriculture/env/`](src/kaggriculture/env/) provides typed Observation dataclasses, action builders, a legality checker for diagnostics, and constants transcribed from `kaggle-environments >= 1.32.7`.

## Reproducibility

- Environment pinned via `uv.lock`.
- Replay data versioned with DVC.
- Every A/B evaluation is a config plus a git commit plus a fixed set of episode seeds.
- Experiments tracked in MLflow (local file store).
- The evaluation protocol (opponent pool, episode count, rating system, significance test) is defined once and reused.

## License

MIT. See [LICENSE](LICENSE).
