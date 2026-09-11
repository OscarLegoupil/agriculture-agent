# Independent review of the capacity gain

The cereal candidate makes a material improvement, but **37.5% against Mooman is
still a losing matchup**. Its mean gap of −713 hides a median gap of −12,856 and a
strong dependence on one tomato-rich seed. The result supports continued work on
productive capacity and diversification; it does not establish current-field
parity or live leaderboard strength.

The comparison freezes V8 `64fe3239`, fleet `9400f9b0` and cereal `c2b3162d`.
All use the same pinned opponents, eight known development seeds and both seats.
The official interpreter is 1.32.7, SHA-256 `bc8a5487…653e`. The
[saved evidence](results/breakthrough-capacity-review.json) contains full hashes,
matched configurations, every seed and both seats. These are development results;
the uncertainty does not adjust for previous candidate selection or opponent
coverage.

| Opponent | V8 wins / mean gap | Fleet wins / mean gap | Cereal wins / mean gap |
|---|---:|---:|---:|
| COK | 6/16 / −4,602 | 14/16 / +15,561 | 16/16 / +23,780 |
| Seyam | 16/16 / +21,277 | 16/16 / +29,532 | 16/16 / +30,455 |
| Mooman | 0/16 / −24,383 | 0/16 / −21,957 | 6/16 / −713 |

The [canonical Mooman comparison](results/breakthrough-capacity-mooman-summary.json)
reports a seed-block 95% score interval of 12.5–75% for cereal. Both seats remain
together within each resampled seed. No difficult opponent is removed or
reweighted here.

## The improvement is not a permanent wheat farm

The frozen source differs from fleet in three production settings: it removes
the fifty-crop ceiling, raises the wheat valuation boost threshold from eight
to 24 planned wheat, and switches the pre-day-15 opening preference from berries
to wheat once 34 berries are planned. The scheduler and its 65 ms optional route
budget are unchanged.

This creates **more usable crop positions and more positions that can change
crop later**. In the Mooman seed-5000 seat-0 witness, fleet ends day 14 with
43 berries and seven wheat; cereal has 34 berries and 23 wheat. From day 15,
cereal converts those positions into tomatoes. By day 20 it has 24 tomatoes
against fleet's seven. Keeping all 23 positions permanently in wheat would
remove the main opportunity exploited in this game.

Across the historical pool, mean wheat receipts increase by 3,882 and total
wheat spending falls by 3,305 per game. That is substantive grain/feed value,
although the spending total combines purchased grain and seed. Tomato receipts
rise by only 1,596 on that pool. The historical improvement therefore has a
different composition from the tomato-dominated frontier witness.

## Concentration and timing

These Mooman gaps average the two seats within each seed:

| Seed | Fleet gap | Cereal gap | Paired improvement |
|---|---:|---:|---:|
| 5000 | −20,018 | +76,384 | +96,402 |
| 5001 | −15,950 | −20,958 | −5,008 |
| 5002 | −35,686 | −30,687 | +4,999 |
| 5003 | −29,002 | −12,559 | +16,443 |
| 5004 | −24,029 | −15,901 | +8,128 |
| 5005 | −6,377 | +2,155 | +8,532 |
| 5006 | −5,744 | +9,015 | +14,759 |
| 5007 | −38,848 | −13,153 | +25,695 |

Seed 5000 contributes **56.7% of the net paired gap improvement**. Excluding it
as a sensitivity calculation—not a revised benchmark—leaves cereal at 4/14 with
a mean gap of −11,727. Seven of eight seed means still improve over fleet, so
the entire gain is not an isolated outlier. The nearly level overall mean is.

Reconstruction of all 32 fleet/cereal Mooman replays verifies **46,016 bilateral
cash transitions** against saved observations. The reconstructed candidate
ledgers also match the benchmark telemetry. No new game or random transition
is sampled.

| Days | Mean change in our receipts | Mean change in our spending | Mean improvement in cash gap |
|---|---:|---:|---:|
| 0–9 | 0 | +4.5 | −4.5 |
| 10–19 | +286 | −1,753 | +2,533 |
| 20–29 | +20,833 | −1,062 | +18,715 |

**88.1% of the paired gap gain arrives in the last ten days.** In that period,
mean tomato receipts rise by 13,717, wool by 8,491 and wheat by 2,058, while
berry receipts fall by 4,852. Mooman also gains 3,186 in late receipts on average;
the result is not simply transferring a fixed revenue total from the opponent.

## What the selected games actually show

**5000: spare crop capacity becomes valuable only much later.** The first
recorded action difference is day 10, hour 19. Cereal remains 24,066 behind at
the end of day 23 and 4,778 behind after day 26. It ends 68,413 ahead in this
seat after earning 110,345 from tomatoes during days 20–29, versus fleet's
17,854. The fourth shop changes from brunch to pizza on day 12. Extra tomato
capacity and stronger realized tomato demand occur together; the replay does
not isolate their individual contributions.

**5001: grain does not compensate for the missing late berries.** The first
action difference is day 12, hour 2. By day 13, cereal has 34 berries and
23 wheat; fleet has 43 berries and seven wheat. Neither policy realizes tomato
income. In seat 0, cereal's late berry receipts fall from 27,896 to 22,651 while
late wheat receipts rise from 3,155 to 4,748. Its gap is better than fleet's on
day 19, but worse at the finish: −20,649 versus −15,950. The grain preference is
not universally the best use of those nine berry positions.

**5002: the capacity change does not repair the earlier income deficit.** The
first action difference is day 9, hour 3. Cereal ends day 14 with 34 berries,
23 wheat, thirteen cows, two sheep and three geese; fleet has 43 berries,
seven wheat, sixteen cows and two sheep. Neither earns tomato income. By day 16,
cereal is already 25,251 behind Mooman. Late grain, carrots and eggs recover
some value, but the final gap is −30,687. Cereal's middle-period milk receipts
are 6,591 against fleet's 13,101; its current milk price falls from 197 on day 12
to one on day 21. The changed herd and market path cannot be separated by this
observational comparison. More crop positions alone do not fix the opening
and livestock income timing documented in the
[earlier fleet diagnosis](breakthrough-fleet-mooman.md).

**5005: the narrow win is primarily a wool-demand story.** Cereal first buys four
additional wheat seeds on day 10, hour 10, with otherwise identical recorded
worker actions. Its fourth shop is yarn on day 12, against fleet's farmers
market. Cereal's late wool receipts rise from 23,613 to 50,722, while tomato
receipts fall from 17,784 to 5,665. The final margin is only 2,155 in both seats.
This win supports an interaction with demand; it is not evidence that every
profitable capacity increase must become tomatoes.

**5006: the additional tomato positions matter again.** Cereal first raises a
wheat seed order from one to four on day 11, hour 16. It remains 22,315 behind at
the end of day 23 in seat 0. Late tomato receipts rise from 19,102 to 43,476,
offsetting a decline in late berry receipts from 43,413 to 32,659; the final
margin is +8,885. The new trajectory receives a second pizza shop on day 18,
where fleet receives farmers market. Again, capacity and demand both change.

## Two limits on causal attribution

**Every matched Mooman game changes the realized town sequence.** The first
difference occurs on day 12 in eight games, day 15 in six and day 21 in two.
The official `_end_of_day` draws weeds before drawing the next shop from the
same day-specific random generator. Different empty tiles therefore change the
shop draw even with the same seed. These are legal competition trajectories;
they are not fixed-demand ablations.

**Runtime fallbacks can change the opening before the crop intervention.**
Against Seyam on seed 5006, seat 0, fleet records ten route-budget fallbacks and
cereal none. Their first action difference is already day 0, hour 1, and their
first shops differ. On that exact recorded observation, both frozen policies
choose the same `PICKUP COW` with ample optional route time. Setting only that
budget to zero reproduces fleet's recorded `BUILD_PASTURE` action and the
different last-hand move exactly. This is a recorded-state diagnostic, not a
new game or a competitive result. That pair contains a load-sensitive fallback
effect as well as the production change. Controlled, interleaved confirmation
should retain fallback events and comparable concurrency.

## Smallest useful next diagnostic

A fixed-shop experiment is designed in the evidence file but **has not run**.
Use seeds 5000 and 5001, both seats, both frozen policies, and two donor shop
schedules: the recorded fleet sequence and the recorded cereal sequence. This
is sixteen explicitly offline games against the reacting pinned Mooman agent.

Wrap the official `_end_of_day`: execute it normally, including growth,
inventory transfer and actual weed draws, then replace only a newly appended
shop with the corresponding donor entry. Reveal it at the normal time. Keep the
full donor schedule only in the diagnostic environment; neither policy receives
future shops. Do not fix prices, inventories, positions or opposing actions.

Compare policies within each donor schedule, then schedules within each policy.
First require the donor-policy controls to reproduce no-fallback witnesses.
If fallback differences alter those controls, an exact causal decomposition is
not supported. Exclude every modified-environment score from the historical
pool, challenge pool and promotion evidence. A persistent advantage under both
donors would strengthen the production hypothesis; disappearance under fleet's
town would identify demand sensitivity as the larger remaining risk.

## Reproduce

```powershell
python scripts/review_capacity_mechanism.py
python scripts/review_capacity_mechanism.py --reuse-cache
```

The first command reconstructs the saved fleet/cereal Mooman transitions,
compares all matched manifests and runs the small recorded-state budget check.
The second validates replay/helper hashes and reuses those ledgers. Neither
command launches a complete game. The final confirmation still needs fresh
seeds, consistent runtime conditions and opponents that contest tomatoes and
wool; local wins against related public-history agents do not establish ladder
strength.
