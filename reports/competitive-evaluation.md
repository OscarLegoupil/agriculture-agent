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

The local executable truth is kaggle-environments 1.32.7. Full benchmark
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

## Frozen holdout result

The frozen artifact completed the holdout once: 128 seeds, both seats and three
opponents, 768 games. The primary score is **65.234%**, with a 95% paired-seed
bootstrap interval of **59.956% to 70.508%**. The predeclared local promotion
gate passes. No production or scheduling parameters changed after opening it.

| Opponent | Wins / games | Score | 95% seed interval | Mean cash gap | 10th-percentile gap |
|---|---:|---:|---:|---:|---:|
| lonespear | 155 / 256 | 60.55% | 52.34–68.75% | +6,402 | −8,630 |
| GzmCR | 179 / 256 | 69.92% | 62.50–77.34% | +4,979 | −14,025 |
| TinaawhyteD | 256 / 256 | 100% | 100–100% | +89,206 | +74,482 |

The crop-only interval is degenerate because every sampled seed wins. It does
not imply zero future loss probability. This reference is much weaker than
the two primary opponents and carries no primary weight.

All 768 games completed normally. Every cash ledger reconciles exactly;
there are zero failed worker operations, logged fallbacks, storage overflows,
or stranded carried/shed units. Maximum decision time was 66.764 ms, and the
largest per-game 99th percentile was 3.553 ms. Local configuration allows one
second per action. These timings and the 24 MB isolated RSS measurement provide
local headroom, but do not establish hosted image or resource compatibility.

Realized footprint peaks near 48 productive tiles, with one successful land
purchase in every game. Mean daily-hire transactions total 281–287 per season;
these are repeated daily hires, not simultaneous worker counts. Against the
primary opponents, labor costs average 5,002–5,176 coins, successful work
2,586–2,661 actions, and travel 3,809–3,859 moves per game.

There is still an execution and planning gap: mean pre-terminal water deaths
are 8.4 crops per game and animal escapes 0.2–0.4. Another 1.3 animals escape
in the terminal window. Telemetry labels events from day 28 onward separately;
timing alone cannot establish that each abandonment is economically optimal.
Natural within-day crop decay is not included in the water-death counter, and
unsold products still on tiles are not included in stranded carried/shed stock.
Zero invalid actions therefore does not mean zero missed opportunity.

An additional 24-game diagnostic reran the exact final artifact on the four
audit development seeds against itself and pinned lonespear variants. The
mirror scores 50% (three wins, two draws, three losses); `main_bigherd.py`
scores 8/8 and `main_v23.py` 7/8. All games completed without candidate errors
or logged fallbacks. These related variants carry no weight in the independent
holdout score. Both the earlier pre-repair stress run and final run are retained.

The worst cash gaps are −16,615 against lonespear (10025, seat 1) and −25,096
against GzmCR (10083, seat 1). Those games had no invalid work, respectively
eight and seven water deaths, and one terminal escape each. This evidence
does not isolate a causal explanation for the market-dependent gap. Further
work should test maintenance opportunity cost and demand diversification on
new development data before using a new holdout.

The full local suite passes 305 tests, with one optional MLflow test skipped.
Lint, formatting, strict typing, standalone process checks and deterministic
artifact regeneration pass. The original v5 artifact remains unchanged.

## Reproduction and remaining publication checks

Detailed records are compressed losslessly in `reports/results/*.json.gz`;
the readable index records their uncompressed hashes and game counts. Summaries
and exact candidate source snapshots remain committed. The earliest exploratory
screens have less complete provenance than the final benchmark manifests;
their exact executable snapshots are preserved, and they are not promotion
evidence. Reference pins are in `reports/reference-manifest.json`.

Run `scripts/figures.py` to regenerate quantitative figures from saved records.
Run `scripts/diagnose_benchmark.py reports/results/holdout-v7.json --output
data/interim/diagnostics.json` for realized execution aggregates. Readers
transparently resolve the compressed file. Full replays were retained locally
for preselected holdout seeds 10000 and 10017; other games can be replayed from
their recorded pins, effective seed and exact candidate snapshot. Replaying a
frozen result is a reproducibility check, not another independent sample.

Kaggle authentication was unavailable. No legal terms were accepted and no
submission was uploaded. After authentication, eligibility and quota checks,
the remaining command is `kaggle competitions submit kaggriculture -f
submissions/20260909-v7/main.py -m "v7 joint assignment"`, followed by submission
status and live replay inspection. The local competitive target passed; hosted
performance remains unmeasured. Historical phase-allocator feasibility and
route-generator milestones are not claimed complete by the new policy.
