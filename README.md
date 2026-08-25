# kaggriculture

Applied autonomous-agent work on the [Kaggriculture](https://www.kaggle.com/competitions/kaggriculture) simulation competition. Two agents compete on separate farms across a 30-day, 720-turn season on a dynamic market. The deliverable is a Python `agent(obs)` function submitted to Kaggle. This repository is a working project, not a submission notebook. It exists to demonstrate a reproducible, engineering-grade workflow from environment analysis to a competitive agent.

## Status

Early scaffolding. See open issues and milestones for the current plan.

## Quickstart

Prerequisites: Python 3.11+, [uv](https://docs.astral.sh/uv/), Git, and a Kaggle account with API credentials configured (`~/.kaggle/kaggle.json`).

```bash
git clone https://github.com/OscarLegoupil/agriculture-agent.git
cd agriculture-agent
uv sync --extra dev
uv run pytest
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

## Reproducibility

- Environment pinned via `uv.lock`.
- Replay data versioned with DVC.
- Every A/B evaluation is a config plus a git commit plus a fixed set of episode seeds.
- Experiments tracked in MLflow (local file store).
- The evaluation protocol (opponent pool, episode count, rating system, significance test) is defined once and reused.

## License

MIT. See [LICENSE](LICENSE).

