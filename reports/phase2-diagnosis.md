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

## Mixed-herd expansion and a sustained cash bridge

The next screen preserves the incumbent's mixed production family while
correcting finite crop valuation, input-stock targets, hour-23 planting, and
nightly delivery. Three variants use 12 hired hands and a three-quadrant cap:
four cows/six sheep/eight geese with 40 or 50 crop tiles, and a goose-led
two-cow/four-sheep/fourteen-goose farm with 44 crop tiles. Crop selection uses
current-demand values with a modest 1.3 strawberry bias, avoiding the preceding
experiment's imposed fourfold berry preference. A bounded early herd and ten
opening wheat plants follow the short-cycle opening hypothesis.

Twenty-four paired games on known seeds 17/103 give:

| Farm | Seyam wins / 4 | Mean cash gap | COK wins / 4 | Mean cash gap |
|---|---:|---:|---:|---:|
| Mixed, 40 crops | 0 | −21,101 | 0 | −71,900 |
| Mixed, 50 crops | 0 | −6,577 | 0 | −67,486 |
| Goose-led, 44 crops | 2 | +2,454 | 0 | −69,984 |

The mixed farms really reach their 40/50 crop targets and 18 animals; these
are not paper allocations that remain undeployed. The goose-led farm reaches
44 crops and 20 animals against Seyam but only 30 crops against COK. The land
occupancy trigger is not reached before the day-15 investment cutoff, so it
never buys its third quadrant in those COK games despite later available cash.

The opening diagnosis is more revealing than the target farm size. Against
Seyam seed 17, the 40-crop variant has 16 melons and four strawberries by day 5,
cash 669, and only five animals by day 10. The initial wheat is replaced by
slow crops immediately after day 3; the nominal liquid opening therefore does
not sustain cash flow until the herd matures.

An eight-game extension keeps ten wheat plants through day 9 in the 50-crop
variant. The predicted mechanism improves: day-5 cash becomes 1,379 and day-10
animals become 12 against Seyam seed 17. The measured competitive result still
fails: 0/4 against each reference, mean gaps −15,740 against Seyam and −52,414
against COK. Relative to the corresponding 50-crop control, paired gap changes
are −9,163 and +15,072. Earlier herd growth is insufficient by itself, and
opponent reactions must be included when evaluating cash-flow interventions.

No variant is promoted. All 32 games finish without failed worker actions or
stderr; maximum action time is 118.9 ms. Reproduce the screens with:

```powershell
uv run python scripts/phase2_mixed_expansion.py --workers 3
uv run python scripts/phase2_mixed_expansion.py --names cashbridge50 --output data/raw/phase2-cashbridge.json --workers 3
```

Full manifests are `data/raw/phase2-mixed-expansion.json` and
`data/raw/phase2-cashbridge.json`. They preserve exact candidate snapshots,
parent opening/production source hashes, configurations, daily realized
production, transaction ledgers, and runtime records.

## Early recurring cohorts before competitor supply

The final production probe removes animal purchases until day 6 and plants
strawberries in every non-wheat opening slot. It sustains eight or ten wheat
plants through day 13, then introduces a small six- or eight-animal herd.
The hypothesis is to sell an earlier berry wave while funding maintenance from
short crops, rather than following the competing public agents' later cohorts.
The variants target 45 and 55 crop tiles on three quadrants with 12 hands.

The first four complete games, seed 17 seat 0 against Seyam and COK for each
variant, are decisively weak screening results:

| Variant | Own / Seyam cash | Own / COK cash |
|---|---:|---:|
| 45 crops, two cows/two sheep/four geese | 40,580 / 82,863 | 35,150 / 120,250 |
| 55 crops, two sheep/four geese | 47,011 / 138,213 | 32,713 / 135,867 |

The early-cohort mechanism is real: 15–17 strawberries are established by day
5, with cash 1,668–1,930 and no watering deaths. It does not establish successful
market preemption. Cash falls to 159–450 by day 10 and remains only 1,463–3,477
by day 15 while expansion and delayed herd purchases consume receipts. Against
COK, 135–136 strawberries sell at mean realized prices of approximately 65–73.
The 45-crop variant never buys its third quadrant and peaks at 42 crops.
Idle actions reach 1,738–1,917 per game, so insufficient raw labor is not the
main explanation.

Input transactions also deserve scrutiny before further production search:
against COK, the 45-crop variant buys 163 fertilizer units, collects 126, uses
94 and sells 195. Purchases cost 12,495 and sales return 14,334. The resulting
ledger is consistent, but the large buy/sell flow raises a specific hypothesis
about low-cash input liquidation followed by replenishment; aggregate totals
alone cannot prove the timing or avoidable loss.

The remaining twelve planned games are unnecessary for promotion screening
given cash gaps of 42,283–103,154 in these probes. This is an early rejection,
not a confidence-bound claim. Whole-policy interventions change the opponent's
responses and can also change realized shop paths through the official
environment; these comparisons do not hold future shop draws fixed.

Reproduce the four-game probe with
`uv run python scripts/phase2_preemption.py --stage probe`. A separate explicit
`--stage followup` command supports the unrun twelve-game extension. Exact
sources and the four-game manifest are saved in
`data/raw/phase2-preemption.json` and `reports/sources/`. All four games complete
without failed worker actions or stderr; maximum observed decision time is
10.8 ms.
