# kaggriculture

Applied machine learning on the Kaggriculture Kaggle challenge. This repository is a working project, not a submission notebook. It exists to demonstrate a reproducible, engineering-grade workflow from raw data to a documented model.

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
├── configs/           experiment configs (YAML)
├── data/              raw, interim, processed (gitignored, DVC-tracked)
├── notebooks/         numbered, single-purpose analysis notebooks
├── reports/           figures, model cards, writeups
├── src/kaggriculture/ installable package
└── tests/             pytest suite
```

## Approach

The project is organized as a sequence of milestones, each tracked by GitHub issues:

1. Project scaffolding and tooling
2. Data acquisition and validation
3. Exploratory analysis and problem framing
4. Baseline model and evaluation harness
5. Feature engineering
6. Modeling iterations
7. Final model, model card, reproducibility check
8. Portfolio writeup

Each modeling iteration is tracked as an issue stating a hypothesis, closed with a comment reporting the result.

## Reproducibility

- Environment pinned via `uv.lock`.
- Data versioned with DVC.
- Experiments tracked in MLflow (local file store).
- Every reported result maps to a git commit and a DVC data version.

## License

MIT. See [LICENSE](LICENSE).
