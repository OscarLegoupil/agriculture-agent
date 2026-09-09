# Kaggriculture

**80.9% validation match score across four pinned public opponents**, up from 52.9% for the previous experimental champion on matched scenarios. The paired improvement is **27.9 percentage points [95% CI: 23.8-32.0]**. Crop-financed expansion and deadline-aware execution achieve 100% against the two anchors and 61.7% against the harder challenge pool. **V8 remains experimental:** its 32.0% COK score fails the predeclared 40% matchup floor. These are local simulator results, not a live leaderboard rating.

![A real game rendered by the official Kaggriculture environment](reports/figures/gameplay.png)

*v7 on the left, pinned lonespear on the right. Seed 0, day 21. Rendered from an actual replay with the official environment; [frame provenance](reports/figures/gameplay.json).*

## The problem

[Kaggriculture](https://www.kaggle.com/competitions/kaggriculture) is a two-player farming simulation. Each player starts with 3,000 coins and 25 usable tiles on a 10 × 10 farm. Crops take time to mature, animals need feed and care, and daily worker costs follow a Fibonacci sequence. Both farms sell into the same market: profitable production can destroy its own selling price.

Only final cash counts. A valuable crop that cannot be harvested, carried home and sold in time is worth nothing. The optimization problem couples **investment, scheduling, working capital and market exposure**.

## The solution

```mermaid
flowchart LR
    O[Observed farms, cash and market] --> E[Finite-season investment gates]
    E --> T[Tasks, deadlines and input reservations]
    T --> M[Joint worker assignment]
    M --> A[Worker actions and market orders]
    A --> O
    classDef state fill:#edf3f6,stroke:#265777,color:#193349
    classDef policy fill:#e0f0ec,stroke:#168477,color:#193349
    class O,A state
    class E,T,M policy
```

The deployed policy lives in [one self-contained module](src/kaggriculture/agent/competitive.py). It rebuilds decisions from observations, preserving actual asset ages, inventories and cash without hidden episode state.

**Finite-season investment.** New crops receive no revenue before maturity. Calendar gates value all five commercial crops; an explicit startup cohort rule favors wheat, melons and early berries. Animal purchases account for remaining production events, feed expense and market exposure. Cash reserves constrain purchases; future shop demand uses expected draws, never future realized state.

**Coordinated execution.** Minimum-cost assignment matches workers to distinct destinations using task value, urgency, travel and pickup costs. Seeds, stored inputs and delivery capacity are reserved. The solver prepares a valid greedy fallback and checks a 150 ms budget during execution. Transition instrumentation exposes invalid actions and resource losses.

**Measured production choices.** An initial melon and wheat cohort finances recurring crops and a shared livestock allocation. V8 permits three total plots, 12 hired workers, 50 crops and 18 animals. These are investment ceilings, not guaranteed purchases. Current experiments test a fourth plot, commissioning speed, earlier herd investment and grown feed. Larger farms and more workers must earn their cost in official games.

**Cash at the finish.** The last action is day 29, hour 22. There is no final nightly inventory drop. Return trips and sales must fit the remaining action opportunities.

**Market and capital.** The policy projects shared-market inventory from observable assets and expected shop demand. Purchases reserve cash for existing obligations. Annual crops receive useful watering before harvest, imminent feeding deadlines reserve feasible input routes, and fertilizer reserves follow upcoming recurring harvests. This remains an approximate economic model; it does not guarantee optimal schedules or future demand.

## Evidence

### Current validation: a large gain with a remaining matchup deficit

Frozen v8 and the previous experimental champion each played 64 seeds (3000-3063), both seats, against four pinned opponents: **1,024 games**. All completed normally with zero candidate stderr. The equal-four score gives each opponent 25% weight. Anchor and challenge pools are also reported separately. Seyam and COK share public route ancestry and are not two independent strategy families.

![Matched validation scores with seed-cluster uncertainty](reports/figures/phase3-validation-matchups.png)

| Opponent | Pinned revision | Previous wins / 128 | V8 wins / 128 | V8 mean cash gap |
|---|---|---:|---:|---:|
| [lonespear](https://github.com/lonespear/kaggriculture/tree/774b26093ccf4246525517d48420349b841b6e50) | `774b260` | 126 | 128 | +43,804 |
| [GzmCR](https://github.com/GzmCR/Kaggriculture/tree/6a76335397d5cd2facffa91c938f629b119ea350) | `6a76335` | 117 | 128 | +41,180 |
| [Seyam](https://github.com/Seyamalam/Kaggriculture/tree/8b8c421eb10634c756583ce10c75189f50c83a72) | `8b8c421` | 26 | 117 | +15,461 |
| [COK](https://github.com/COK-ZhangZiliang/Kaggriculture/tree/7ef67eac458cd9ecd13786063e2e581fbe7403ec) | `7ef67ea` | 2 | 41 | -4,528 |

V8's equal-four score is **80.86% [77.54-83.98%]**. Confidence intervals resample complete seeds, retaining both seats, opponents and policies together. Draws count as half a win. The COK floor fails despite a large improvement; the final holdout remains unopened. The inspected validation seeds are now development data for the next candidate, with fresh validation reserved at 4000-4063.

![Measured cash, production and worker actions](reports/figures/phase3-validation-behavior.png)

Loss diagnosis separates missing early production, costly purchased feed and slow expansion from controller defects. Broader known-data checks rejected immediate delivery, depot reserves and joint feeding despite encouraging small screens. In inspected fourth-plot games, COK reaches 87-90 productive tiles versus v8's 68 while paying less for labor. Current experiments therefore test land utilization and production timing, with separate labor ablations. They do not assume three additional purchases always pay.

[Validation protocol](reports/phase3-confirmation-protocol.json) | [Results and uncertainty](reports/results/phase3-validation-summary.json) | [Current research protocol](reports/phase4-protocol.md) | [Land diagnosis](reports/phase4-land.md) | [Earlier research and negative results](reports/phase2-results.md).

### First-cycle release holdout

The unchanged v7 release previously achieved **65.2%** on its original holdout, with a 95% interval of **60.0–70.5%**. That holdout is now known development data; it is not fresh evidence for the second cycle.

The primary score weights lonespear and GzmCR equally. TinaawhyteD provides an independently implemented crop-only check with no primary weight. Mirrors and supply-heavy variants are diagnostics, not additional independent opponents.

![Per-opponent scores and paired-seed confidence intervals](reports/figures/performance-v7.png)

| Holdout opponent | Pinned revision | Wins / games | Mean v7 cash | Mean opponent cash |
|---|---|---:|---:|---:|
| [lonespear, livestock-led mixed](https://github.com/lonespear/kaggriculture/tree/774b26093ccf4246525517d48420349b841b6e50) | `774b260` | 155 / 256 | 87,779 | 81,377 |
| [GzmCR, mixed farming](https://github.com/GzmCR/Kaggriculture/tree/6a76335397d5cd2facffa91c938f629b119ea350) | `6a76335` | 179 / 256 | 84,560 | 79,581 |
| [TinaawhyteD, crop-only](https://github.com/TinaawhyteD/kaggriculture-agent/tree/169ca945b3358cd85baa71260e9c17dc0ebe5555) | `169ca94` | 256 / 256 | 108,239 | 19,033 |

Development used 16 seeds and validation used 64. The frozen artifact then played the 128-seed holdout once: 768 games, including both seats against all three opponents. Confidence intervals resample complete seeds, retaining both seats and both primary opponents together. Draws count as half a win. The predeclared promotion gate passed: lower 95% bound above 50%, no candidate errors and no independent strategy family below 40%. [Protocol and experiment record](reports/competitive-evaluation.md) · [holdout summary](reports/results/holdout-summary.json) · [validation summary](reports/results/validation-final-summary.json) · [compressed evidence index](reports/results/index.json).

### What changed from v5

The original four-tile v5 beat starter but lost against every independent reference in the diagnostic panel. It remains unchanged. The same four development seeds show both improvement and a difficult matchup:

| Opponent | v5 wins | v7 wins | v5 mean cash | v7 mean cash |
|---|---:|---:|---:|---:|
| Starter | 8 / 8 | 8 / 8 | 9,121 | 112,552 |
| lonespear | 0 / 8 | 8 / 8 | 8,653 | 78,667 |
| GzmCR | 0 / 8 | 2 / 8 | 8,326 | 93,333 |
| TinaawhyteD | 0 / 8 | 8 / 8 | 9,338 | 108,302 |

*Seeds 0, 17, 42 and 103, both seats. This small development panel is not the promotion test. Source versions, executable hashes and effective configuration are saved with the results.*

![Cash and productive footprint across the season](reports/figures/trajectories-v7.png)

The important gain was executable production. The old static allocator also credited immature crops with average daily income and excluded commercial wheat. Those assumptions are corrected and tested against the interpreter. Earlier phased planning and route controllers remain available for historical comparison; v7 does not deploy them.

### An ablation that changed the design

![Joint assignment versus greedy worker scheduling](reports/figures/assignment-ablation.png)

Joint assignment reduced mean travel from 4,250 to 3,841 moves and increased successful work from 2,377 to 2,597 actions. Match score rose from 37.5% to 75% across eight games per candidate. This small paired development panel justified broader testing; it is not the headline strength estimate.

More land, more workers and larger herds did not consistently pay. Strawberry-heavy expansion, early goose-first openings and harvest batching also lost their screens. A pickup/drop loop and a same-turn reservation bug were execution defects, not evidence against livestock. Fixes have dedicated regressions.

## Reproduce it

Python 3.11 or 3.12 and [uv](https://docs.astral.sh/uv/) are required. The lockfile pins `kaggle-environments==1.32.7`.

```bash
uv sync --frozen --extra dev
uv run pytest tests/test_competitive_smoke.py -q
```

The second command is the one-command smoke evaluation: both frozen v7 and v8 artifacts play starter in both seats (four games). `make smoke` runs the same check where Make is available.

Fetch the reviewed references and run a paired benchmark:

```bash
uv run python scripts/fetch_references.py
uv run python scripts/benchmark.py --candidate submissions/20260909-v8/main.py --opponents data/raw/reference-lonespear/main.py data/raw/reference-gzm/main.py --seeds 0 17 42 103 --output data/interim/reproduction.json
uv run python scripts/summarize_benchmark.py data/interim/reproduction.json
```

Reproduce the historical v7 production search, verify current v8 packaging and regenerate the historical release figures:

```bash
uv run python scripts/search_production.py --stage 1 --output data/interim/production-search.json
uv run python scripts/package_submission.py
uv run python scripts/verify_submission.py --output data/interim/packaging-check.json
uv run python scripts/figures.py --evaluation reports/results/holdout-v7.json
uv run python scripts/diagnose_benchmark.py reports/results/holdout-v7.json --output data/interim/diagnostics.json
uv run python scripts/render_replay.py --screenshot
```

The screenshot command needs Chrome or Chromium (`--chrome PATH` selects it). It also exports an interactive official HTML replay into ignored `reports/replays/`. Compressed results are read transparently. Restore an exact historical executable with `scripts/restore_candidate.py SHA256`, using its manifest's digest.

Reproduce current validation with the frozen v8 artifact and the exact seeds/opponents in [the protocol](reports/phase3-confirmation-protocol.json). Restore historical candidates using their SHA-256 snapshots; do not rebuild them from a changing development policy. The previous experimental champion is `0098d9e4f77e2420cb4a09abd47e49f5160009cd0818ae37a793bc3e419ffc4b`.

## Reliability and boundaries

The [current standalone experimental artifact](submissions/20260909-v8/main.py) is built deterministically from the deployed source. SHA-256:

```text
64fe323936dc9494add413eb956b0294658a88efe28572332c94676c68a09325
```

V8 packaging checks cover 2,876 actions along four complete source/artifact trajectories, 60 observations in two fresh isolated Python processes, and state reset. Peak current-image memory was 24,801,280 bytes on Windows and 23,506,944 bytes in Linux CI. Linux `/proc/self/status` avoids counting inherited pre-exec memory as policy memory. These local measurements do not certify hosted limits. [Packaging evidence](reports/results/phase3-packaging-final.json) | [Linux measurements](reports/results/phase3-linux-ci.json).

Across 512 v8 validation games, maximum recorded action time was **113.925 ms**, with zero errors or stderr. The immutable [v7 rollback](submissions/20260909-v7/main.py) retains hash `750f123073865347efd3b9c4b72022ff9923f4130c929ac76c1b0742374b09ee` and its historical holdout evidence. V8 has not passed the broader release gate.

CI checks lint, formatting, types, interpreter contracts, execution regressions, complete games, standalone verification and deterministic regeneration. Run the checks locally:

```bash
uv run ruff check .
uv run ruff format --check .
uv run mypy src
uv run pytest
```

The economic forecast is a compact heuristic, not an exact optimal season plan. V8 repairs the earlier late-planting and deadline defects but still fails the COK qualification floor. Terminal escape counts are reported separately; this timing classification does not prove abandonment was optimal. The expanded benchmark includes a weak independent crop-only reference and two harder opponents with shared public route ancestry. It does not represent the full live field. Local execution does not establish a leaderboard rating or verify the current hosted image and resource limits.

Kaggle authentication was unavailable, so no live submission was made. The following command submits the v7 rollback that passed its historical release protocol. V8 remains experimental and has not qualified on the expanded field. Authentication, eligibility and quota must be available:

```bash
kaggle competitions submit kaggriculture -f submissions/20260909-v7/main.py -m "v7 joint assignment"
kaggle competitions submissions kaggriculture
```

## Repository guide and attribution

| Location | Purpose |
|---|---|
| `src/kaggriculture/agent/competitive.py` | Deployed policy and bounded assignment solver |
| `submissions/20260909-v8/` | Current frozen experimental artifact and manifest |
| `submissions/20260909-v7/` | Immutable release rollback |
| `submissions/20260902-v5/`, `submissions/20260908-v6/` | Preserved historical submissions |
| `scripts/` | Evaluation, production search, packaging and figures |
| `tests/` | Game contracts, failure regressions and integration checks |
| `reports/results/`, `reports/sources/` | Compressed evidence, summaries and exact candidate snapshots |
| `data/raw/`, `data/interim/`, `reports/replays/` | Ignored reference checkouts, working data and large replays |

The [official Kaggle interpreter](https://github.com/Kaggle/kaggle-environments/tree/master/kaggle_environments/envs/kaggriculture) supplies game rules and rendering. Public references informed strategic hypotheses and are evaluated in isolated checkouts; their implementations are not included in the submission. lonespear is MIT-licensed, copyright Jonathan Day. Original licenses and public-route attribution remain in the checkouts; other reference source is not redistributed. [Anchor pins and hashes](reports/reference-manifest.json) · [challenge pins and provenance](reports/challenge-reference-manifest.json).
