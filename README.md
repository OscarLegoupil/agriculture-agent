# Kaggriculture

**89.8% validation match score against the two primary public anchors**, up from the incumbent's 69.9% on matched scenarios. A larger, market-aware farm delivers a paired gain of **19.9 percentage points [95% CI: 10.9–29.3]**. The harder challenge pool exposes the remaining gap: **13.3%**, below the 50% promotion gate. The challenger remains experimental; v7 is the release and rollback. These are local simulator results, not a live leaderboard rating.

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

**Finite-season investment.** New crops receive no revenue before maturity. All five commercial crops compete for planting slots. Animal purchases account for remaining production events, feed expense and market exposure. Cash reserves constrain purchases; future shop demand uses expected draws, never future realized state.

**Coordinated execution.** Minimum-cost assignment matches workers to distinct destinations using task value, urgency, travel and pickup costs. Seeds, stored inputs and delivery capacity are reserved. The solver prepares a valid greedy fallback and checks a 150 ms budget during execution. Transition instrumentation exposes invalid actions and resource losses.

**Measured production choices.** Official-interpreter screens explored land, labor, crop-only and livestock-only policies, animal mixes, fertilizer, grown feed, openings and delivery thresholds. Selected capacity bounds are two quadrants, 11 hired workers, up to 30 crops and a herd of four cows, six sheep and eight geese. These are ceilings; observed state and economic gates determine purchases.

**Cash at the finish.** The last action is day 29, hour 22. There is no final nightly inventory drop. Return trips and sales must fit the remaining action opportunities.

**The research challenger.** The second cycle repairs late planting and input accounting, permits affordable partial feed purchases, releases fertilizer reserves when cash is scarce, and projects shared-market inventory from observable assets and expected shop demand. Combining those changes with capacity for 50 crops, three quadrants and 12 hired workers improves the measured anchors. The forecast remains an approximate servicing scenario; it is not an exact forward simulator. The [frozen builder](scripts/build_phase2_challenger.py) reproduces the experimental artifact without changing the deployed module.

## Evidence

### Second-cycle validation: stronger, but not promoted

Both frozen policies played seeds 2000–2063, both seats, against four pinned opponents: **1,024 games**, with no execution errors. Anchors and challenges are separate equal-weight pools; difficult opponents were retained. Seyam and COK share a public route lineage, so they are not counted as two new independent strategy families.

![Incumbent and challenger on the same validation scenarios](reports/figures/phase2-validation.png)

| Opponent | Pinned revision | v7 wins / 128 | Challenger wins / 128 | Challenger mean cash gap |
|---|---|---:|---:|---:|
| [lonespear](https://github.com/lonespear/kaggriculture/tree/774b26093ccf4246525517d48420349b841b6e50) | `774b260` | 94 | 123 | +24,413 |
| [GzmCR](https://github.com/GzmCR/Kaggriculture/tree/6a76335397d5cd2facffa91c938f629b119ea350) | `6a76335` | 85 | 107 | +16,475 |
| [Seyam](https://github.com/Seyamalam/Kaggriculture/tree/8b8c421eb10634c756583ce10c75189f50c83a72) | `8b8c421` | 5 | 31 | −11,408 |
| [COK](https://github.com/COK-ZhangZiliang/Kaggriculture/tree/7ef67eac458cd9ecd13786063e2e581fbe7403ec) | `7ef67ea` | 0 | 3 | −35,259 |

The anchor score is **89.84% [85.16–94.14%]**; the challenge score is **13.28% [8.20–18.75%]**. Complete-seed bootstrap intervals retain both seats, both policies and all opponents. Draws count as half a win; none occurred. The primary-anchor improvement and local reliability checks pass, but the challenge floor fails. The new holdout remains unopened. Supplementary Tina was not rerun in this panel; its crop-only results below remain historical.

![Realized cash and crop capacity during validation](reports/figures/phase2-validation-trajectory.png)

The challenger harvests more and reduces watering deaths from 8.97 to 0.71 per game, but travels farther and loses more animals before the terminal window. More cash and a larger farm do not establish broad competitive strength. Against COK, its 10th-percentile cash gap remains −55,669.

Small matched ablations showed an interaction: liquidity plus expansion won 0/8 challenge games; liquidity plus the forecast won 2/8; all three won 4/8. Broader validation confirmed the anchor gain but reduced Seyam's selected development score from 58.3% to 24.2%. Crop-first openings, service bundles, adaptive livestock, speculative holding and marginal-price-impact investment did not earn promotion. [Research results and ablations](reports/phase2-results.md) · [frozen protocol](reports/phase2-protocol.md) · [validation data and uncertainty](reports/results/phase2-validation-summary.json) · [independent review](reports/phase2-independent-review.md).

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

The second command is the one-command smoke evaluation: the frozen artifact plays starter in both seats. `make smoke` runs the same check where Make is available.

Fetch the reviewed references and run a paired benchmark:

```bash
uv run python scripts/fetch_references.py
uv run python scripts/benchmark.py --candidate submissions/20260909-v7/main.py --opponents data/raw/reference-lonespear/main.py data/raw/reference-gzm/main.py --seeds 0 17 42 103 --output data/interim/reproduction.json
uv run python scripts/summarize_benchmark.py data/interim/reproduction.json
```

Search production choices, verify packaging and regenerate figures:

```bash
uv run python scripts/search_production.py --stage 1 --output data/interim/production-search.json
uv run python scripts/package_submission.py
uv run python scripts/verify_submission.py --output data/interim/packaging-check.json
uv run python scripts/figures.py --evaluation reports/results/holdout-v7.json
uv run python scripts/diagnose_benchmark.py reports/results/holdout-v7.json --output data/interim/diagnostics.json
uv run python scripts/render_replay.py --screenshot
```

The screenshot command needs Chrome or Chromium (`--chrome PATH` selects it). It also exports an interactive official HTML replay into ignored `reports/replays/`. Compressed results are read transparently. Restore an exact historical executable with `scripts/restore_candidate.py SHA256`, using its manifest's digest.

Reproduce the second-cycle challenger and its saved comparisons with the commands in [the research report](reports/phase2-results.md#reliability-and-reproduction). The exact research hash is `0098d9e4f77e2420cb4a09abd47e49f5160009cd0818ae37a793bc3e419ffc4b`; the v7 release remains `750f123073865347efd3b9c4b72022ff9923f4130c929ac76c1b0742374b09ee`. CI rebuilds and checks both artifacts in clean processes. The research candidate recorded a 158.2 ms maximum decision, zero errors, zero stderr and zero observed assignment fallbacks across its 512 validation games. Hosted performance remains unverified because Kaggle authentication is unavailable.

## Reliability and boundaries

The [standalone artifact](submissions/20260909-v7/main.py) is built deterministically from the deployed source. SHA-256:

```text
750f123073865347efd3b9c4b72022ff9923f4130c929ac76c1b0742374b09ee
```

First-cycle packaging compared 2,876 actions along four complete source/artifact trajectories, then 60 observations in two fresh Python processes without site packages or repository imports. Windows isolated peak RSS was about 24 MB. In that original holdout, decisions took at most 66.8 ms; all 768 games finished with zero agent errors, failed worker actions, logged fallbacks, storage overflow or stranded shed/carried inventory. Every cash ledger reconciled. [First-cycle packaging](reports/results/packaging-final.json) · [holdout diagnostics](reports/results/holdout-diagnostics.json).

Second-cycle Linux CI passed **315 tests**, with one optional MLflow skip, and independently rebuilt and verified both artifacts. Linux resource-based peak RSS was 242.5 MB for v7 and 251.1 MB for the challenger. These platform-specific measurements are recorded separately from the Windows result and do not certify hosted resource limits. [Cross-platform CI evidence](reports/results/phase2-linux-ci.json).

CI checks lint, formatting, types, interpreter contracts, execution regressions, complete games, standalone verification and deterministic regeneration. Run the checks locally:

```bash
uv run ruff check .
uv run ruff format --check .
uv run mypy src
uv run pytest
```

The economic forecast is a compact heuristic, not an exact optimal season plan. The retained v7 release still has the late-planting defect isolated in the second cycle; the experimental challenger repairs it but fails the broader promotion gate. Terminal escape counts are reported separately; this timing classification does not prove abandonment was optimal. The expanded benchmark includes a weak independent crop-only reference and two harder opponents with shared public route ancestry. It does not represent the full live field. Local execution does not establish a leaderboard rating or verify the current hosted image and resource limits.

Kaggle authentication was unavailable, so no live submission was made. After authenticating and confirming eligibility and quota, submit the exact validated file:

```bash
kaggle competitions submit kaggriculture -f submissions/20260909-v7/main.py -m "v7 joint assignment"
kaggle competitions submissions kaggriculture
```

## Repository guide and attribution

| Location | Purpose |
|---|---|
| `src/kaggriculture/agent/competitive.py` | Deployed policy and bounded assignment solver |
| `submissions/20260909-v7/` | Standalone artifact and manifest |
| `submissions/20260902-v5/`, `submissions/20260908-v6/` | Preserved historical submissions |
| `scripts/` | Evaluation, production search, packaging and figures |
| `tests/` | Game contracts, failure regressions and integration checks |
| `reports/results/`, `reports/sources/` | Compressed evidence, summaries and exact candidate snapshots |
| `data/raw/`, `data/interim/`, `reports/replays/` | Ignored reference checkouts, working data and large replays |

The [official Kaggle interpreter](https://github.com/Kaggle/kaggle-environments/tree/master/kaggle_environments/envs/kaggriculture) supplies game rules and rendering. Public references informed strategic hypotheses and are evaluated in isolated checkouts; their implementations are not included in the submission. lonespear is MIT-licensed, copyright Jonathan Day. Original licenses and public-route attribution remain in the checkouts; other reference source is not redistributed. [Anchor pins and hashes](reports/reference-manifest.json) · [challenge pins and provenance](reports/challenge-reference-manifest.json).
