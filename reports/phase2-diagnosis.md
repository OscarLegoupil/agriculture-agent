# Competitive loss diagnosis — 9 September 2026

The frozen incumbent is v7, SHA256
`750f123073865347efd3b9c4b72022ff9923f4130c929ac76c1b0742374b09ee`.
This analysis uses the previous cycle's holdout as **known development data**.
It supplies hypotheses, not a new generalization claim.

## Main findings

The largest strategic uncertainty is demand-sensitive production allocation.
Across the 512 primary-opponent games, the 178 losses have **more own cash**
than the 334 wins: 91,510 versus 83,324. Mean feed, care, harvest and hiring
quantities are nearly identical. Mean milk income is 28,354 in losses versus
15,497 in wins; wool income reverses that relationship, 15,355 versus 20,999.
These are confounded associations, not causal effects, but they point toward
matchup and market specialization rather than a global lack of worker capacity.

Lonespear seed 10017 illustrates the problem. Both seats lose 122,434 to
131,362 despite no missed watering of established crops in the exact replay
diagnosis. At day 2 the opening has three cows, two sheep and six melons; day 5
cash is only 206, and day 10 cash is 990. The fixed four-cow ceiling persists
while milk eventually contributes 29,856. The testable hypothesis is that an
opening with better capital recovery and subsequent demand-sensitive herd
allocation can improve this regime. Future realized shop draws must never
enter the deployed forecast.

There is also a concrete planting-admission defect. Across eight saved games
(seeds 10000 and 10017, both seats against the two primary references), exact
official transitions identify **70 watering deaths: 65 newly planted crops
die immediately on hour 23, and five established crops miss watering**.
New crops start with one unwatered day, so planting on the final daily action
without a later worker watering them causes an immediate death. The first
occurrence is already day 0. The 65 failed plantings consume 2,390 in seed
cost across the eight games, plus planting and recovery work. This is not an
estimate of recoverable final cash; alternative actions and market responses
change the subsequent trajectory.

The earlier aggregate `water_deaths` label is **correct for these events**.
It must not be relabeled as exhausted-crop decay. A naive adjacent-state
replay comparison misses same-turn planting and death altogether, and instead
observes 46 unrelated exhausted zero-yield crop transitions plus one positive-
yield decay. The diagnostic script replays recorded worker actions, decay and
daily plant refresh through the official helper functions, asserting that
every reconstructed plant matches its stored next state. This resolves the
otherwise misleading discrepancy. Historical telemetry remains unchanged.

## Controlled counterfactuals

Twenty-four complete official games change one component at a time. Each
candidate faces the same two opponents, seeds 10000 and 10017, and both seats
as the incumbent. Opponents run normally and can react to the changed farm and
market; these are not fixed-opponent-action replays. Only four games per
opponent are available, with strong within-seed dependence, so no confidence
or promotion claim is made.

| Change | Lonespear wins / 4 | Lonespear paired cash-gap change | GzmCR wins / 4 | GzmCR paired cash-gap change |
|---|---:|---:|---:|---:|
| Incumbent | 2 | — | 2 | — |
| Existing-crop watering priority 115 → 200 | 2 | −7,129 | 1 | −4,935 |
| Feed pickup quantity 3 → 6 | 2 | −5,830 | 4 | +13,202 |
| Exclude mandatory delivery workers from matching | 2 | −9,519 | 3 | +3,338 |

The baseline mean cash gaps are +7,280.5 against lonespear and −154.25 against
GzmCR. These results reject a blanket watering-priority increase. Larger feed
pickups merit an opponent-independent workload or delivery-cost condition,
rather than unconditional promotion. Removing delivery workers from matching
is logically cleaner but does not itself establish better outcomes: trajectories
and market responses matter, and the two opponents disagree strongly.

Exact candidate hashes:

- Water urgency: `3028742fc62c3e86e244ae28a08a609e4f271493cc5ceba9a0c9c9a92f8dd465`
- Larger feed pickups: `798879a5024cadee7d67f4fc1affcc46d689c9c430b55d969ec32fb35961e16c`
- Delivery exclusion: `d85ef6b62ba91e47b3a9357595f0ed0593c94278fafcd4306a3c54a2344f3bba`

## Ranked experiments

| Priority | Hypothesis | Expected impact and uncertainty | Effort | Smallest informative experiment |
|---|---|---|---|---|
| 1 | Current herd caps and startup cash allocation miss favorable market regimes | Potentially large; correlation only, so high uncertainty | Medium | Compare legal current-demand-driven herd allocation and shorter-payback openings on known milk-rich and wool-rich regimes, including newly measured strong references |
| 2 | Admit planting only when a watering opportunity remains | Proven correctness defect; direct seed savings modest, downstream effect unknown | Small | Reject hour-23 planting and test paired trajectories; then reserve a feasible watering action for late new cohorts |
| 3 | Input deliveries should depend on downstream service workload and distance | Mixed causal screen: strong Gzm gain and lonespear regression | Medium | Bound pickup quantity by reachable unserved animals and remaining daily actions, comparing travel, feeding and cash against fixed three/six-unit pickups |
| 4 | Matching should include the opportunity cost of delivery and task prerequisites | Logically justified, but simple exclusion loses on one reference | Medium | Jointly score delivery destinations with farm tasks, reserve physical stock, and compare the combined change against each component |
| 5 | Increase generic maintenance priority | Negative screen; low priority | Small | Reject this version; only revisit with deadline-specific evidence |

Saved replays contain 59–75 immediate movement reversals per game. This is a
diagnostic count, not proof that every reversal wastes work: a changed deadline
or market state can legitimately change the best task. Approximately 3,833
travel moves per loss and 3,835 per win, alongside similar maintenance counts,
do not support claiming that travel alone explains the competitive gap.

## Reproduction

```powershell
uv run python scripts/phase2_diagnosis.py
uv run python scripts/phase2_diagnosis.py --counterfactuals --workers 3
```

The first command analyzes the committed prior holdout manifest and its selected
local replay files. The second regenerates isolated candidate files and runs
the 24-game screen. Detailed output and candidate files are written beneath
`data/interim/phase2-diagnosis/`; `counterfactuals.json` includes executable
hashes, environment and interpreter versions, all matched incumbent records,
and complete candidate telemetry. Selected bulky replay files remain local;
they can be recreated with the benchmark command and seeds above if absent.
The deployed policy is never modified by this script.

## Compatible-service bundle screen

A subsequent 32-game screen tests a larger scheduler change on seeds 17 and
103, both seats, against both anchors and the pinned Seyam/COK challenge
references. Both candidates reject hour-23 planting, value reachable compatible
tasks at a destination together, and anticipate CARE after FEED. The second
also rewards nearby same-input tasks and adjusts feed pickup quantities to
remaining working time. These remain stateless policies using observed state.

| Candidate | Lonespear wins / 4; paired gap change | GzmCR wins / 4; paired gap change | Seyam wins / 4; paired gap change | COK wins / 4; paired gap change |
|---|---:|---:|---:|---:|
| Service bundles | 2; −6,159 | 3; +6,988 | 0; −23,553 | 0; −13,428 |
| Bundles and input routes | 2; −9,164 | 2; −1,588 | 0; −7,460 | 0; −2,075 |

Both are rejected. The first reduces watering deaths from 7.875 to 1.125 per
game, while increasing mean feeding from 398.7 to 408.8 and care from 384.75
to 396.5. Travel rises slightly, from 3,807.25 to 3,818.69 actions. Improving
maintenance counts therefore does not establish competitive improvement.
None of these two candidates wins a challenge-pool game.

The bundle scoring is approximate. In particular, it can credit a watering or
fertilizer follow-up after harvesting an annual crop, even though that harvest
removes the crop. Actual actions remain legal because the next observation
replans from the real field. A future bundle model must treat such harvests as
terminal transitions; the poor challenge results do not justify another large
screen merely to repair this approximation. A more useful direction is a
production plan with reachable service obligations and economic priorities.

All 32 games completed with zero failed worker actions and no stderr/fallbacks.
Maximum observed action time was 154.8 ms; maximum per-game p99 was 21.2 ms.
The extra route scoring has a measurable runtime cost without demonstrated gain.

Reproduce with `uv run python scripts/phase2_work_bundles.py --workers 3`.
The full manifest is `data/raw/phase2-work-bundles.json`; compressed exact
source snapshots are preserved beneath `reports/sources/`:

- Service bundles: `40feb84aa4bbb1683489665d2a1d5dcbbe79dc037b429e6d597edef0c8bb669c`
- Bundles and input routes: `07b0ef88062a963c99f6c0b08d2624a9c7d63c848d059b31f92b4bc7f88ea64e`
