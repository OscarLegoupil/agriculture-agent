# Opening melon dispatch and market share

**11 September 2026.** The dispatch candidate improves opening melon revenue in all
32 inspected matchups without changing the opening farm or growing another melon.
It gets the same crop to market before competing supply depresses prices. This is
a verified mechanism. The completed32-seed development confirmation improves
COK wins from21/64 to37/64 while retaining61/64 against Seyam. A separate matched Mooman panel
ends **0/16 for both incumbent and race**, with the race's mean deficit slightly
worse. The race is a historical-pool challenger, with no demonstrated gain
against the stronger current reference.

The complete measurements, paired cases, artifact identities, and representative
event timelines are in
[the diagnosis JSON](results/breakthrough-melon-diagnosis.json). This report uses
the completed `breakthrough-season-screen` incumbent rows and
`breakthrough-melon-screen` experiment for mechanism and ablation analysis. The
separate `breakthrough-race-mooman` panel and wider historical-pool confirmation
are reported below; the mechanism analysis remains the original eight seeds.

## What was compared

Each policy played COK and Seyam on seeds 5000–5007, in both seats: 32 games per
policy, 128 saved replays. Both opponents are pinned, but share replay-route
ancestry; this panel cannot establish broad opponent coverage.

| Policy | Artifact SHA-256 | Components |
|---|---|---|
| v8 incumbent | `64fe323936dc9494add413eb956b0294658a88efe28572332c94676c68a09325` | Frozen baseline |
| Race | `13f029db938d83caf2c5fdde2341e848ac139b957f343c3a53e683e8115815c2` | Valuable-melon task priority, delivery-worker reservation correction, immediate return, same-turn melon sales |
| Fertilizer + race | `e56e8b7dc4d905580ea68c72e9003cff28b205fcf794885cee80a9dce85bce28` | Race plus early fertilizer reservation, purchase, pickup, and application |
| Fertilizer only | `37b7ba4423b55894cfcf1e9be0989762cf902e23d75152e2d691b589858b6a87` | Fertilizer pipeline with the incumbent dispatch and selling rules |

The manifest name `melon_race_only` includes same-turn melon sales. It is not an
ablation of selling versus dispatch. The individual dispatch changes have not
been isolated by this experiment.

The baseline manifest records revision
`755294e386c00907482a452d9f0d5f8793a7cda9`; the melon manifest records clean revision
`bbecedda99ca29ad926a905d58a017a79f3190b4`. Evaluation used
`kaggle-environments==1.32.7`, the same interpreter hash, dependency lock, effective
configuration, opponent executable hashes, and resolved seeds. The intervening
harness changes add provenance and entrypoint checks; the episode execution and
telemetry implementation are unchanged.

## The decisive change happens at maturity

All 32 race games match the incumbent's complete game state through day 10, hour
0. In one case the first changed action is hour 1. Initial planting, land,
workers, cash, crop ages, and observed shops therefore cannot explain the early
gain. The first consequential intervention is the assignment of workers to ripe
melons, including watering before harvest when the last yield increment is still
available.

| Mean across 32 games | Incumbent | Race | Fertilizer + race | Fertilizer only |
|---|---:|---:|---:|---:|
| First harvest, day-10 hour | 9.34 | 5.00 | 4.00 | 6.69 |
| First sale, day-10 hour | 16.19 | 10.00 | 9.00 | 12.69 |
| Melons sold on day 10 | 53.63 | 71.44 | 71.63 | 32.63 |
| Day-10 melon receipts | 12,230 | 16,697 | 16,958 | 7,782 |
| Melons in shed at day-11 start | 16.13 | 0.56 | 0.38 | 30.38 |
| Total seasonal melons sold | 84 | 84 | 84 | 84 |

The race harvests all 72 opening-cohort melons on day 10 in every game. The
incumbent averages 69.75 harvested that day and sells fewer still. Its workers
can reserve another task during matching before the delivery branch overrides
their action, leaving other workers without that assignment. The race excludes
melon carriers from matching, gives ripe melons an economic priority, and sells
verified deposits in the same turn.

For COK seed 5000, seat 0, the incumbent first harvests at hour 9 and deposits
24 melons at hour 15; the sale waits until hour 16. The race begins harvesting at
hour 5, sells its first six at hour 10, and sells all 72 by hour 20. Its day-10
melon receipts rise from 11,047 to 16,505. These are realized worker actions and
executed market transactions, not requested-order quantities.

## The gain is mostly market share

The opponent still sells exactly the same seasonal melon quantity in each paired
case: 72 for COK and 120 for Seyam. The race also retains its own 84-unit total.

| Mean change versus incumbent | COK matchup | Seyam matchup | Equal-weight pool |
|---|---:|---:|---:|
| Own melon receipts | +2,916 | +958 | +1,937 |
| Opponent melon receipts | −2,946 | −1,005 | −1,976 |
| Cash-margin gain from melon receipts | +5,862 | +1,963 | +3,912 |
| Final cash-margin gain | +6,747 | +2,482 | +4,614 |

Melon receipts account for 84.8% of the observed mean cash-margin improvement;
combined bilateral melon receipts change by only −39. Own seasonal melon income
and bilateral melon cash margin improve in all 32 cases. This supports earlier
capture of the shared market as the principal mechanism. The decomposition is
an accounting identity, not a controlled estimate of every causal effect.

## Why fertilizer fails to earn its place

The fertilizer implementation works mechanically: all 12 opening melons reach
the six-unit cap before day-10 actions, and the policy makes 14 successful melon
applications over the season. Ordinary melons reach that same cap by watering
immediately before harvesting. Fertilizer therefore adds no realized seasonal
yield.

With race enabled, fertilizer advances the first harvest and first sale by one
turn, adding just 261 mean day-10 melon receipts. It spends 715 on fertilizer
purchases during days 6–9, before counting application, pickup, travel, or the
opportunity cost of retained manure. Day-10 starting cash falls from 1,312 to
986. Strawberry plants fall from 24.19 to 22.31, while cows plus sheep fall from
8.12 to 7.22. These changes already exist before the melon harvest: this is a
working-capital and scheduling interaction, not a free maturity improvement.

Fertilizer alone also exposes a priority defect. An uncapped ripe melon gets the
incumbent's 140-priority watering task, drawing a worker toward its location.
Once fertilizer has capped it, that task is no longer required and the harvest
has priority 70. The first fruit is harvested earlier, but the farm processes
the full cohort much more slowly: only 32.63 melons sell that day, versus 53.63
without fertilizer. Earlier first harvest alone would have selected the wrong
policy.

The race incurs some wider opportunity costs: mean commercial wheat sales fall
from 91.34 to 83.28 units. It does not increase observed nonterminal animal
escapes (eight across each 32-game panel), and water deaths decline from ten to
eight. The full fertilizer package has 16 nonterminal escapes and 28 water
deaths. These are aggregate observations; changed subsequent markets and farm
choices prevent assigning every later loss to one worker action.

## Competitive evidence and its limits

| Policy | COK wins / 16 | Seyam wins / 16 | Weighted score | Mean own cash | Mean cash gap |
|---|---:|---:|---:|---:|---:|
| Incumbent | 6 | 16 | 68.75% | 78,943 | +8,338 |
| Race | 11 | 16 | 84.38% | 79,663 | +12,952 |
| Fertilizer + race | 6 | 16 | 68.75% | 81,089 | +11,110 |
| Fertilizer only | 3 | 15 | 56.25% | 77,596 | +3,972 |

There were no draws. COK and Seyam each receive 50% weight. The race's paired
score improvement is **+15.63 percentage points, with a 95% seed-cluster
bootstrap interval of −3.13 to +34.38 points**. Its paired own-cash improvement
is +721 [−4,085, +5,706]; its cash-margin improvement is +4,614
[+1,852, +6,954]. The bootstrap resamples eight seed clusters, retaining both
seats, both opponents, and the candidate/incumbent pairing together. Its 20,000
resamples use fixed RNG seed 1729. These exploratory intervals do not correct
for candidate selection or quantify uncertainty about opponent coverage.

Identical seeds also do not mean identical future shops. The official daily
refresh draws weeds for empty cells before drawing the next shop from the same
daily RNG. Different harvest and replacement schedules change the number of
draws. All 32 race pairs eventually have different shops: 22 first diverge on
day 12, six on day 15, and four later. No deployed decision uses those future
draws. Nevertheless, final score changes include this response of the actual
game. For example, COK seed 5000 becomes a win while own cash falls 15,476;
opponent cash falls 27,722. A single favorable score flip would overstate the
evidence.

The historical screen justifies wider investigation. It does not justify
promoting fertilizer or claiming a live rating gain. Further
dispatch-versus-selling ablations would identify which parts of the simpler
package are necessary.

### The stronger current opponent rejects a frontier claim

The declared extension to5008–5031 is complete. Combining it with the original
eight seeds gives128 matched games per policy, with no repeated attempts chosen
for their outcome. The [confirmation summary](results/breakthrough-race-field-summary.json)
retains source identities and per-opponent distributions.

| Development5000–5031, both seats | Incumbent wins | Race wins | Mean cash-gap change | Paired95% interval |
|---|---:|---:|---:|---:|
| COK | 21/64 | 37/64 | +5,612 | +3,242 to+7,921 |
| Seyam | 61/64 | 61/64 | +2,733 | −77 to+5,627 |

Equal-weight score rises64.06%→76.56%, a12.50-point paired gain with95% interval
3.91–21.09 points. COK alone gains25.00 points [9.38,40.63]; Seyam's zero score
change has interval−6.25 to+7.81 points. Whole-seed bootstrap clusters retain
both seats, opponents and policies. There are no draws, errors or stderr turns;
the largest candidate action is121.42ms. These are development results after
screen selection, not a fresh-validation or holdout claim.

The completed, separate Mooman panel uses the same frozen incumbent and race
artifacts, seeds 5000–5007, both seats, and the same official configuration. Its
manifest records revision `a1ea464abe602b9fdf34471ccd33218df8854811`; the Mooman
executable and imported data/module hashes are retained in the diagnosis JSON.

| Against pinned Mooman | Wins / games | Mean own cash | Mean cash gap |
|---|---:|---:|---:|
| Incumbent | 0 / 16 | 72,725 | −24,383 |
| Race | 0 / 16 | 72,661 | −25,333 |

All games finish normally with zero candidate stderr. The race's mean deficit
widens by 950. These are development seeds and the small panel does not establish
the exact size of a regression, but it clearly supplies no evidence of a
competitive breakthrough against Mooman. The current reference already executes
an early melon sale pipeline; matching that behavior leaves the previously
diagnosed production and labor gap unresolved. Neither the historical score gain
nor the verified melon-market mechanism should be presented as current-frontier
or live-ladder improvement.

## Independent checks

- Every executable equals its frozen compressed source snapshot and expected
  SHA-256. The official source loader selects the intended `agent` callable.
- Re-evaluating 1,920 recorded observations reproduces every recorded action,
  including both seats, opening, maturity, and final-day states. No stderr is
  emitted; the slowest audit call takes 50.75 ms. These calls do not advance the
  simulator or reveal later state to the policy.
- Recorded actions were applied to copied states through the official unit and
  market helpers. All 10,818 inspected bilateral cash balances agree with the
  next recorded observation; reconstructed own melon receipts reconcile exactly
  with telemetry. Both players' melon sales are reconstructed in the same pass.
- All 128 games finish `DONE` for both players with zero candidate stderr. The
  race's slowest recorded call is 61.82 ms; its largest per-game p99 is 4.27 ms,
  against the configured one-second action limit. These are local measurements,
  not hosted execution or leaderboard evidence.

The frozen sources, raw manifests, replay hashes, aggregate intervals, per-case
differences, and representative event sequences are retained in the linked
result file. Rebuild the diagnosis from the saved manifests and replays with:

```bash
python scripts/diagnose_melon_screen.py
```

The command executes recorded actions on copied states and audits recorded
observations; it runs no games. `--help` lists the manifest, replay-directory,
cache, and output overrides. `--reuse-cache` checks the analysis source,
manifests, candidate bytes, and every replay hash before reusing the saved
accounting. Improving the larger production and worker-service economy remains
necessary to close the Mooman gap.
