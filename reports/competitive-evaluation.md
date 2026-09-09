# Competitive evaluation

## Protocol frozen before validation

Optimize match score, with a win worth 1, draw 0.5 and loss 0. Errors count as
losses. Report final cash separately; it is not a substitute for match outcomes.

Development seeds: 0, 17, 42, 103, 5, 11, 23, 31, 47, 61, 79, 97, 127, 151,
181, 211. The first four were used in the earlier audit. Cheap screens use the
first two seeds, both seats, and eliminate grossly inferior configurations.
Validation seeds: 1000 through 1063, both seats. Holdout seeds: 10000 through
10127, both seats. Do not run holdout until the executable and configuration
are frozen. If holdout informs tuning, retire it.

The primary suite weights lonespear main and GzmCR main equally. Both are
independent implementations with livestock and mixed production. Tina's
crop-only agent is a supplementary family check, with a 40% score floor.
Starter, v5, v6, mirrors and lonespear's larger-herd variant are diagnostic
controls, not independent votes in the primary score. There is no verified
strong independent crop-only opponent yet; this limits coverage.

Promotion requires a lower 95% confidence bound above 0.50 on the weighted
primary score, zero candidate execution errors, and no measured independent
strategy family below 0.40. Bootstrap complete seeds, including both seats and
all primary opponents together, with 10,000 deterministic resamples. Also
report the lower 10th percentile cash gap and individual opponent scores.
Validation chooses the candidate. Holdout tests that frozen choice once.

Initial compute budget: 48 games per broad production screen; up to 256 games
for targeted development; 384 games for a three-opponent validation panel;
768 games for its holdout. Full games currently take approximately 2 to 6
seconds with two processes. Stop screens that clearly lose; do not use large
panels to confirm an obvious failure. Changes to this budget must be recorded.

## Sources and isolation

The local executable truth is kaggle-environments 1.32.7. Every benchmark
manifest records its interpreter SHA-256, effective configuration, resolved
seed, executable hashes and repository revision. Reference repositories live
in ignored `data/raw/` and are never imported by the deployed policy.

| Reference | Revision | Executable | License handling |
|---|---|---|---|
| [lonespear](https://github.com/lonespear/kaggriculture) | `774b26093ccf4246525517d48420349b841b6e50` | `main.py` | MIT, Jonathan Day; license retained in clone |
| [GzmCR](https://github.com/GzmCR/Kaggriculture) | `6a76335397d5cd2facffa91c938f629b119ea350` | `main.py` | Isolated original checkout; no source redistributed |
| [TinaawhyteD](https://github.com/TinaawhyteD/kaggriculture-agent) | `169ca945b3358cd85baa71260e9c17dc0ebe5555` | `agent.py` | Isolated original checkout; no source redistributed |

The references inform hypotheses about working capital, market saturation,
care, fertilizer and delivery. The new policy is implemented separately.
Configurations of a reference are stress tests, not independent opponents.

## Starting evidence

The current base is `549e81e`, eight commits ahead of origin/main. It already
contains v6, phased routes and a multi-worker scheduler. V5 and v6 remain
unchanged. The structure-per-animal fix already exists on this base; the
average-ROI horizon and wheat-exclusion defects remain in its static model.

All 101 existing planning/submission tests pass. Six additional tests exercise
the interpreter itself. The four-seed audit has 8 games per opponent:

| Candidate | Opponent | Wins | Mean cash | Mean opponent cash |
|---|---|---:|---:|---:|
| v5 | starter | 8/8 | 9,120.75 | 3,487.00 |
| v5 | lonespear | 0/8 | 8,652.62 | 105,407.88 |
| v6 | starter | 8/8 | 81,148.38 | 3,628.50 |
| v6 | lonespear | 0/8 | 60,575.25 | 87,071.25 |

Starter results reproduce the supplied v5 audit exactly. External-reference
cash differs from the supplied audit despite the same package version and
reference revision; retain manifests rather than silently equating the runs.
All episodes completed normally. This panel is development evidence only.

## Interpreter contracts

Workers act in index order before the market; new purchases and hires become
usable next turn. Excess PLANT requests cancel all planting of that crop.
Movement through locked land is legal. Seeds are shared; feed, fertilizer and
animals must be picked up. One structure holds one animal. Held-product caps
are not housing capacities. CARE banks a bonus after that day's production,
so today's care does not affect tonight's output. Two missed water/feed days
kill crops or release animals.

Ongoing crops have four scheduled production events, not perpetual output.
Fertilizer lasts three days inclusive and doubles an ongoing production only
when the preceding day was watered. With prompt harvesting, strawberry can
produce eight units. Decay removes one held unit every two turns after the
lifespan step. Existing assets retain their observed ages and stored yields.

The last actionable observation is step 718, day 29 hour 22. It is followed by
terminal step 719, hour 23. There is no last nightly drop. DROP resolves before
SELL in the same turn, but storage overflow happens before those sales. Only
cash scores. Final return trips must fit the remaining action opportunities.

Market orders are capped at ten, execute per unit with price impact, and use
shared pre-commit quotes for both seats. Inputs can cost more than the displayed
quote because purchases use the post-buy price. Land unlocks NE/SW/SE for
1,000/2,000/4,000. Shops are random draws with replacement, at most eight;
forecasts may use observed shops and expected future draws, never realized
future state. Opponent fields are public; opponent inventories are private.

The official local configuration allows one second per action plus 60 seconds
of overage. Hosted memory/image and live eligibility still require verification.
Kaggle's overview and discussion pages did not expose readable bodies through
the browser; the installed interpreter and official repository documentation
were used instead. Documentation describing fixed BUY_PRODUCT prices conflicts
with the executable dynamic purchase curve.

## Experiment record

Screen 01 revealed a feed pickup/drop loop: the delivery threshold counted
needed inputs as produce. Fixing that prerequisite handling increased seed-0
cash from roughly 37,000 to 73,000 and preserved the herd. The first screen
remains a rejected candidate, not a benchmark success.

The broad screen varies land, labor, crop-only production, herd-only production,
cow/sheep/goose mix, fertilizer and grown feed. Saved outputs, not hand-entered
chart values, are the source for subsequent comparisons.

The second screen favored 4 cows, 6 sheep and 8 geese (5/8 primary-suite wins)
over the 8-cow, 6-sheep control (1/8). On seeds 42/103, lowering the delivery
threshold from eight to five units improved the primary cash gap from -8,035
to +1,178, with 4/8 wins. More labor and larger herds failed to improve it.
Harvest batching then lost 12/16 and was rejected. Early goose-first openings
also underperformed. These are selection data, not confidence intervals.

A joint minimum-cost worker assignment won 6/8 on seeds 5/11 versus the greedy
delivery control's 3/8. This is the first substantial scheduler improvement
against both independent references. Extend the targeted-development budget
from 256 to 512 games to check it across the full 16 development seeds and
diagnose remaining losses before validation. The primary protocol, seed splits
and promotion threshold remain unchanged. The full initial test suite passes:
296 tests, with optional MLflow tracking skipped because it is not installed.

GitHub publication: draft PR #65. Issue #59 was reopened; duplicate #64 was
consolidated into #62. Kaggle CLI reported authentication required, so no hosted
submission or live leaderboard claim is available from this environment.

The joint-assignment candidate finished development at 24/32 against lonespear
and 17/32 against GzmCR. The candidate is now frozen for validation as artifact
`4d4cfc3413a452997c16cfa44a3711d7fba04e5223d94bec402d8b77ae5235e9`.
Packaging compared 2,876 source/artifact actions along four complete trajectories,
plus 60 observations in two clean Python processes with site packages disabled.
All actions matched. Peak traced Python allocations were approximately 3.1 MB;
this is not a measurement of full process RSS or a verified hosted memory limit.
The assignment solver has a precomputed valid greedy fallback and checks its
150 ms budget inside augmenting-path iterations; fallback use is logged to stderr.

Validation of that artifact scored 64.06% (95% seed-block interval 55.86% to
72.27%): 87/128 wins against lonespear, 77/128 against GzmCR and 128/128 against
the supplementary crop reference. There were no agent errors or logged
fallbacks; all cash ledgers reconcile exactly. Three PICKUP no-ops exposed
an ordering defect: assignment order differs from interpreter worker order,
so a planned DROP must not replenish another worker's pickup reservation.
The repair reserves pickups only from observed stock and reserves drop capacity
without crediting same-turn pickups. A focused interpreter-state regression
test covers this case. Revalidation is required for the repaired hash;
holdout remains unopened. This adds 384 validation games to the compute budget,
without treating the repeated validation seeds as new evidence.

The repaired artifact `750f123073865347efd3b9c4b72022ff9923f4130c929ac76c1b0742374b09ee`
completed all 384 revalidation games with the same match scores and no failed
worker actions, agent errors, or assignment-budget fallbacks. Isolated peak
process RSS measured 23,998,464 bytes. This artifact is selected and frozen
before opening seeds 10000 through 10127. No policy changes are permitted
based on those holdout outcomes without retiring the holdout.
