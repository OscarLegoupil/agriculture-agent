# kaggriculture

[![CI](https://github.com/OscarLegoupil/agriculture-agent/actions/workflows/ci.yml/badge.svg)](https://github.com/OscarLegoupil/agriculture-agent/actions/workflows/ci.yml)

Autonomous-agent work on the [Kaggriculture](https://www.kaggle.com/competitions/kaggriculture) Kaggle simulation. Two players compete on separate farms across a 30-day, 720-turn season on a dynamic market. This is a working project, not a submission notebook: reproducible workflow from environment analysis to a competitive agent.

## Progress

- [x] **M1** foundations, CI, deps, smoke test
- [x] **M2** typed env wrappers, action legality checker, 5 dynamics notebooks
- [ ] **M3** evaluation harness (parallel runner, Bradley-Terry rating, A/B testing)
- [ ] **M4** rule-based baselines
- [ ] **M5** economic planning core (per-tile ROI, allocator, feed budgeting)
- [ ] **M6** market and opponent modeling
- [ ] **M7** advanced planner
- [ ] **M8** submission, hardening, final writeup

## The environment at a glance

![Market price curves for all 9 resources](reports/figures/market-curves-grid.png)

Sell prices react to inventory shifts with different shapes on each side of the equilibrium `I0`. Premium goods (strawberry, melon, milk, wool) crash to the $1 floor on modest gluts. Carrot, tomato, and egg use a `hinge` shape that spikes sharply past a threshold on scarcity. Wheat is the only near-linear resource, and the only staple.

<table>
<tr>
<td width="50%">

![Crop ROI at base prices](reports/figures/crop-roi.png)

Melon leads `$/tile/day` at base prices, but is glut-crash prone. Strawberry gains the most from fertilizer.

</td>
<td width="50%">

![Town demand across 5000 seasons](reports/figures/town-demand.png)

Wheat and strawberry are the most reliably-demanded. Melon has near-zero shop demand. Wool distribution is bimodal because yarn stores may never spawn.

</td>
</tr>
</table>

Details in [`notebooks/`](notebooks/): market curves, crop yields, animal economics, town demand, hire ROI.

## Quickstart

Python 3.11 to 3.12, [uv](https://docs.astral.sh/uv/).

```bash
git clone https://github.com/OscarLegoupil/agriculture-agent.git
cd agriculture-agent
uv sync --extra dev --extra notebooks
uv run pytest
make sim   # runs a full 720-turn episode locally
```

## Repository layout

```
src/kaggriculture/env/    typed observation wrappers, action builders, legality checker
notebooks/                numbered dynamics analysis notebooks
reports/figures/          committed figures produced by notebooks
tests/                    pytest suite
configs/                  experiment configs (YAML, populated as milestones land)
data/                     generated replays and metrics (gitignored, DVC-tracked)
```

## License

MIT. See [LICENSE](LICENSE).
