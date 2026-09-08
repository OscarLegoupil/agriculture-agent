# kaggriculture

[![CI](https://github.com/OscarLegoupil/agriculture-agent/actions/workflows/ci.yml/badge.svg)](https://github.com/OscarLegoupil/agriculture-agent/actions/workflows/ci.yml)

Autonomous-agent work on the [Kaggriculture](https://www.kaggle.com/competitions/kaggriculture) Kaggle simulation. Two players compete on separate farms across a 30-day, 720-turn season on a dynamic market. This is a working project, not a submission notebook: reproducible workflow from environment analysis to a competitive agent.

## Progress

- [x] **M1** foundations, CI, deps, smoke test
- [x] **M2** typed env wrappers, action legality checker, 5 dynamics notebooks
- [x] **M3** evaluation harness: parallel runner, replay logger, per-episode metrics, Bradley-Terry rating, A/B compare CLI, MLflow tracking
- [x] **M4** rule-based baselines: five hand-crafted agents (v0-v4), each closed with a two-agent A/B, plus a round-robin Elo report
- [x] **M5** economic planning core: per-crop and per-animal ROI tables, wheat feed budgeter, static tile allocator, dynamic re-planner
- [x] **M6** market and opponent modeling: price forecaster ([model card](reports/market-forecaster-card.md)) and opponent inventory tracker
- [x] **M7** advanced planner: route + micro-controller + public-state selector, tuned by offline beam search
- [x] **M8-scale** 10x coin scale-up: multi-worker scheduler, phased routes, allocator-driven route generation
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

## Evaluating agents

The eval harness runs pairings in parallel with deterministic seeds and seat swapping, and reports Bradley-Terry Elo, Wilson CIs, and a sign-test p-value.

```bash
uv run kagg-compare pass starter --n 50 --config '{"episodeSteps": 720}'
```

```
=== kagg-compare: pass vs starter ===
episodes: 100  duration: 32.1s  (0.32s/ep)

pass                  W:    0  L:  100  T:   0   win_rate: 0.0%   [95% CI: 0.0%-3.7%]
starter               W:  100  L:    0  T:   0   win_rate: 100.0% [95% CI: 96.3%-100.0%]

sign test (two-sided): p = 1.58e-30
Bradley-Terry Elo (mean 1500):  starter 2100  pass 900  delta +1200
```

Add `--replay-dir data/raw/replays` to save every episode's JSON and a `manifest.jsonl` for downstream analysis. Add `--mlflow` to log to a local MLflow store.

## Baseline ladder

Each baseline exercises one strategic axis and closes its commit with an A/B against its predecessor. A round-robin over all baselines plus the three built-in agents produces the internal Elo ladder:

![Baseline Elo ladder](reports/figures/baselines-elo.png)

- **v0** pure wheat loop, single tile.
- **v1** wheat + carrot on two adjacent tiles.
- **v2** adds one fed and cared goose (coop at (4, 3)), delayed until the wheat pipeline is producing to avoid ramp-up starvation.
- **v3** market-responsive selling and fertilizer reuse. Fertilizer from the goose is applied at the start of each plant's bonus window, lifting wheat cap 4 -> 6 and carrot 3 -> 4.
- **v4** adds a second carrot tile at (3, 3) and one hired hand ($1). Land expansion is available but not automatically triggered at this scale.

Full report and win-rate matrix under [`reports/baselines-elo.md`](reports/baselines-elo.md).

## Economic planning core

M5 turns the dynamics notebooks into a small operations-research layer under `src/kaggriculture/planning/`:

- `crop_roi(crop, watered, fertilized, price)` returns lifecycle units, days to peak, and coins per tile per day. Fertilizer cost is a caller-supplied parameter so animal-produced (free) and market-bought ($100) regimes stay explicit.
- `animal_roi(animal, cared, product_price, feed_cost_per_day)` returns steady-state coins per day and an exact discrete break-even day, computed from a cumulative-net trace rather than the loose continuous formula in the notebook.
- `feed_budget(roster)` projects daily wheat consumption from an `AnimalPlan` list and derives the wheat tile count required to sustain the peak.
- `allocate(tiles, horizon_days, price_map)` enumerates every feasible animal roster and picks the (roster + wheat reserve + best fill crop) combination that maximises expected coins over the remaining horizon.
- `DynamicReplanner` wraps the allocator with a state machine that re-plans when observed prices drift more than `threshold_pct` from the working forecast, and exposes a `replan_frequency` counter for the harness.

The v5+ agents will consume these tables rather than hard-coding tile choices.

## Market and opponent modeling

M6 adds two online modules used by the planner and by the M7 trading layer:

- `src/kaggriculture/market/` ships a `PriceForecaster` that combines the deterministic price curve, the deterministic town consumption schedule, and an EWMA net-trade-rate estimate. Predicted prices plug straight into `DynamicReplanner`'s `price_map`. Aggregate MAE against a five-pairing pool: $0.05 at 1 step, $1.88 at 1 day, $19.3 at 5 days, versus $0.78 / $17.6 / $84.3 for the naive constant-price baseline. Full protocol and per-commodity breakdown in the [model card](reports/market-forecaster-card.md).
- `src/kaggriculture/opponent/` ships an `OpponentInventoryTracker` that reconstructs the opponent's hidden shed from the market inventory ledger (dzjiann's bookkeeping identifier, discussion 737027). Measured MAE across the same opponent pool is exactly zero for every commodity, matching the strong identifiability claim. When a commodity's price sits at the floor the tracker widens the uncertainty interval by the maximum orders the opponent could hide.

![Forecaster calibration at 1, 24 and 120 step horizons](reports/figures/forecaster-calibration.png)

## Advanced planner

M7 layers a portfolio of route configs under `configs/routes/`, a public-state selector, and an offline beam search under `src/kaggriculture/search/`:

- A route is a YAML plan for one 720-turn episode: tile assignments, coop / pasture placement, hire schedule, land buys, market policy, and an optional embedded micro block. `RouteAgent` in `src/kaggriculture/agent/route_agent/` turns any parsed route into a Kaggle-callable `agent(obs)` and reproduces v4_expansion byte-for-byte on fixed seeds.
- `MicroController` overlays M6 forecast and opponent-tracker signals on the route's market policy each turn. Rules are additive-only: hard-drop, forecast-salvage, and tail-salvage. In a paired 400-game A/B this overlay beats plain v4 396-4 at defaults, and 386-14 with tuned parameters (sign test p ~= 2e-95, Elo delta +576).
- `RouteSelector` picks one of four v4 variants after day 3 from opponent tile and land signals. The picked route + a tuned micro layer beats the v4+micro baseline 378-22 on 400 games (Elo delta +494).
- `kaggriculture.search.beam` is a small discrete-grid beam search that tunes route and micro parameters against a target opponent family. It converges on the same configuration the M7-c heuristic picks for the v4+micro family, and the beam-searched YAML at `configs/routes/tuned/v4_micro.yaml` beats plain v4+micro 189-11 on 200 games (Elo delta +494).

## Scale-up

M7 ended at 9604 coins against `starter` and around 300 Elo on the live ladder. The ceiling was structural: the runner gave the main farmer one decision tree and hands a short fixed watering list, so the farm could never grow past the four tiles the farmer's twenty-four turns could reach. M8-scale replaces the runner and re-derives the tile plan, and lands at 82081 coins on the same measurement.

Three things had been mispriced.

**Hands are almost free.** They are cleared every night and the n-th rehire of a day costs `fib(n)`, so nine hands cost 88 coins a day, under one percent of what they harvest. The binding constraint was never money, it was the single-worker runner.

**Every animal is a fertilizer machine.** `fertilizer_available` is set on every surviving animal every day, whatever its species, whether or not it was fed. At a 100 base price that byproduct is worth more than the egg, and it is the largest single revenue line in the game. `animal_roi` did not model it, `allocator._structures_for` divided head count by `max_held` (which caps unharvested produce, not occupancy, so a coop holds exactly one goose), and `allocate` charged for feed twice by reserving wheat tiles *and* subtracting a cash feed cost. All three are fixed.

**Melon is the crop, and only briefly.** A melon hits its six-unit cap at age ten for eight waterings, the best coins per worker-action of any crop, but the price curve is quadratic above `I0` and floors after about 158 units. Ten tiles running two cycles is roughly the whole depth of that market; a twenty-five-tile melon farm sells most of its crop at $1.

The shipped plan is twelve structures on the tiles nearest the shed (four geese, four cows, four sheep), thirteen melon tiles behind them, hands ramping to nine by day 5, and a switch of the melon tiles to carrot on day 20, the last day a fresh melon can still ripen. Feed is bought rather than grown: a wheat tile yields one unit a day and a melon tile earns a hundred.

### Multi-worker scheduler

`src/kaggriculture/agent/route_agent/scheduler.py` replaces the decision tree with a per-turn assignment problem. Every planned tile that wants attention becomes a task with a priority; every worker takes the highest-priority task it can reach in the fewest Manhattan steps.

```
0  water a plant that weeds tonight, feed an animal that escapes tonight
1  harvest ripe crops and animal produce, place a bought animal
2  fertilize a plant inside its bonus window
3  plant an empty plan tile, clear a weed, build a missing structure
4  water a plant whose yield still grows today
5  feed and care for an animal that is not at risk
6  collect fertilizer
7  drop carried produce at the shed
8  pick up feed or an animal from the shed
```

A task that needs a carried item and finds no carrier sends exactly *one* worker to the shed. Without that cap a herd of hungry animals pulls the whole crew into a feed ferry every turn and the crops die untended, which is what the first draft did.

The scheduler holds no state between turns and falls back to an all-`PASS` turn if it overruns a 400 ms budget or the observation will not parse.

### Phased routes

`Route` gained a `phases: list[Phase]` field. A phase restates the whole footprint from a given day rather than a delta, so the file reads top to bottom, and a non-empty `phases` switches `RouteAgent` from the v4 tree to the scheduler. [`configs/routes/expansion_full.yaml`](configs/routes/expansion_full.yaml) is the hand-authored plan the generated one is measured against.

The market policy for a phased route spends in the order feed, animals, seeds, and only grows the herd as far as the wheat already on hand can feed it. An unfed animal escapes after two days and takes the rest of its season income with it; the first version spent its last coin on livestock and then starved the whole herd by day 12.

Paired-seed A/B, 200 games, seat-swapped, against v5: **200-0**, sign test p = 1.2e-60, mean coin gap +70827, Elo delta +1200.

### Allocator-driven route generation

`src/kaggriculture/agent/route_agent/generate.py` derives the same shape from `build_phased_plan` instead of by hand. The allocator decides counts; the generator decides addresses (structures nearest the shed, since they want a daily visit plus a wheat delivery) and adds the two things the allocator cannot express:

- Volume-aware pricing. `Allocation.expected_revenue` is linear in tiles, so repricing alone oscillates between corner solutions: price animals at base and it buys the whole roster, which crashes milk and wool, so the next pass buys none. The generator sweeps a family of herd ceilings and scores every plan with the same volume-aware `plan_revenue`.
- A tail substitution, so a phase starting too late for melons plants something that can still ripen.

```bash
uv run python -m kaggriculture.agent.route_agent.generate \
    --family expansion --opponent starter --top-k 8 --eval-seeds 6
```

The model ranks shapes well and misses the last few percent, so the driver plays the shortlist out and caches the winner in `configs/routes/tuned/`. That distinction is what found the shipped route. The model's own favourite spreads twelve animals evenly across three species; the hand-authored plan is goose-heavy with fifteen. Against `starter` they are within a percent of each other. Against **each other** the even split wins 189-11 over 200 paired seats, sign test p = 5e-43, mean coin gap +7212, because a herd spread across three product markets is not fighting the opponent for the same one. Both agents earn about 60k in that matchup rather than the 82k either earns alone, which is the market depth showing up as a competitive effect rather than a pricing one.

The generated route is what `submissions/20260908-v6/main.py` ships.

## Current submission

`submissions/20260908-v6/main.py` (agent v6) is the packaged M8-scale agent: the scheduler, the phased market policy, and the generated plan as a single self-contained file with no imports of the `kaggriculture` package. A test asserts it reproduces the package agent's rewards exactly on fixed seeds, so a transcription slip cannot pass silently.

Runtime posture: 400 ms per-turn budget with a safe `PASS` fallback on overrun, and a malformed observation returns `PASS` rather than raising. Local smoke test against `starter` on seed 42 finishes at 79600 coins; mean 82175 and worst 79600 across seeds 0-3 and 42.

`submissions/20260902-v5/main.py` is the previous packaged agent (M7): route decision tree, micro tail-salvage, public-state selector. It finishes at 9604 coins on the same smoke test.

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
src/kaggriculture/env/       typed observation wrappers, action builders, legality checker
src/kaggriculture/planning/  ROI tables, feed budget, tile allocator, dynamic re-planner
src/kaggriculture/market/    price curve and online forecaster
src/kaggriculture/opponent/  inventory inference from public state
src/kaggriculture/agent/     shipped agent, its route layers, the scheduler, route generation
src/kaggriculture/search/    offline beam search over route + micro parameters
configs/routes/              route YAMLs (v4 variants, expansion_full, tuned/ cache)
submissions/                 dated Kaggle submission bundles (self-contained main.py)
notebooks/                   numbered dynamics analysis notebooks
reports/figures/             committed figures produced by notebooks
tests/                       pytest suite
configs/                     experiment configs (YAML, populated as milestones land)
data/                        generated replays and metrics (gitignored, DVC-tracked)
```

## License

MIT. See [LICENSE](LICENSE).
