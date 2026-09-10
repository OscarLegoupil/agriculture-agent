# Review before fresh phase-3 validation

The current result justifies fresh confirmation. It does not yet justify a
competitive release or a live-rating claim. This review makes no policy changes
and runs no games.

## Strongest supported claim

Verified the completed 128-game archive
`results/phase3-deadline-field.json.gz` against
`results/phase3-deadline-field-summary.json`: its uncompressed hash is
`400f0f81faacb8238e566aa209e62c29a4df616fadac450e444eb70c14429977`.
The executable snapshot also matches
`59b46457c6511d5df959a95a8c4eb8297e649e0a95b2ae7886f2042e7a60bab3`.
All 128 unique scenarios cover seeds 2000–2015, both seats and all four opponents;
all games finished normally.

| Opponent | Wins / games | Mean candidate cash gap |
|---|---:|---:|
| lonespear | 32 / 32 | +45,963.25 |
| Gzm | 32 / 32 | +46,423.13 |
| Seyam | 28 / 32 | +20,034.28 |
| COK | 14 / 32 | -2,709.97 |

The equal-four score is 82.8125%; the challenge score is 65.625%, compared with
17.1875% for `0098` on those same scenarios. Maximum measured action time is
73.27 ms and no stderr turns were recorded. These are known development seeds
used during strategy discovery. Their bootstrap intervals describe this panel;
they do not correct for repeated selection. COK remains a losing matchup in
point estimate, and the two challenge opponents share implementation lineage.

The anchor bootstrap interval `[1, 1]` is a mechanical consequence of all
observed seed blocks scoring one. It is not certainty about unseen opponents or
seeds. Do not present it without that limitation or turn it into a claim of a
perfect policy.

## Proposed preregistration

Freeze this plan and the final executable identities before starting any fresh
game. The experimental incumbent is
`0098d9e4f77e2420cb4a09abd47e49f5160009cd0818ae37a793bc3e419ffc4b`;
v7 remains the rollback release. The challenger should be the cleaned,
self-contained implementation equivalent to `59b46457...`, with its **actual
new SHA-256 and source revision recorded after parity checks**. A code cleanup
does not inherit the old artifact's byte identity automatically.

Use exactly seeds **3000–3063**, both seats, all four unchanged opponents and
both policies: **512 games per policy, 1,024 total**. Freeze opponent hashes:

| Opponent | Executable SHA-256 |
|---|---|
| lonespear | `3981830b9181db4685afe2b61f182edb13ff5a19d344a70b16a6bc5aedf2a026` |
| Gzm | `fef48be655b403c994979ba1e88eaa550c98ec7e1a7b207c1ceebda990d69c23` |
| Seyam | `4c02a323b0939e8f99df69dc6c23026946b033b0d831c79216ffac0ded9c8e60` |
| COK | `1c7335f698692f1c7bac34913a9ededc0f736dfb2b51346a4fa59098ab471d01` |

Keep `kaggle-environments==1.32.7`, interpreter
`bc8a54879ef02c7ea64b8b333d6a976f0ea65c4949149d01f463f23bccee653e`,
the recorded lock/dependencies and the official effective configuration from
the development archive. Configuration includes 720 episode steps, 24 turns per
day, a one-second action limit, ten market orders and shed capacity 100. Store
the complete configuration, not just those selected fields.

Weights remain 0.5/0.5 within the anchor and challenge pools; report an additional
equal-four aggregate with weight 0.25 each. Do not move weights between pools,
drop COK, or treat supplementary historical opponents as newly validated.
Complete the panel without tuning, selecting variants, or stopping when an
interval becomes favorable. Infrastructure interruptions can resume only the
missing declared scenarios; preserve failed attempts and distinguish them from
candidate errors. A candidate error is evidence, not an automatic rerun request.

## Outcomes, uncertainty and practical gates

Use the existing error-aware match score: win 1, cash draw 0.5, loss 0. Candidate
non-DONE outcomes score zero; an opponent error scores a win only when the
candidate is DONE. Keep failures in score denominators and report both parties'
error counts. Missing cash has no fabricated zero value; exclude it only from
cash statistics and report the missing count. A DONE row with missing or
non-finite cash is an evidence-integrity failure requiring diagnosis.

Use **10,000 deterministic bootstrap resamples**, RNG seed **20260910**, sampling
whole seed blocks. Each sampled block retains both seats, every opponent and
both policies. Use percentile 2.5%/97.5% intervals for paired score changes and
pool scores. Reuse the same blocks for per-opponent score intervals and paired
mean cash-change intervals. Report per-opponent and per-pool point scores,
paired changes, mean/median/10th-percentile cash gaps, missing outcomes, failures,
and runtime distributions. Do not substitute an independent-games binomial
interval or an ordinary unpaired bootstrap. Seed uncertainty and opponent-pool
coverage are separate limitations.

Retain the inherited mandatory gates:

1. Anchor score improvement at least **5 percentage points**, with a strictly
   positive lower 95% paired-seed bound.
2. Each independently implemented primary anchor scores at least **40%**.
3. Challenge score improves and reaches at least **50%** under unchanged weights.
4. Zero candidate errors/timeouts; verified artifact/source trajectory parity,
   clean-directory imports, fresh/reused process reset, and local maximum action
   time below **0.5 seconds**.

For the stronger competitive claim sought in this phase, preregister two
additional safeguards before viewing fresh results: **challenge score lower
95% bound above 50%**, and **each named challenge opponent's point score at least
40%**. These are recommended additions, not requirements already present in
the phase-2 gate. The final frozen protocol must explicitly state whether they
are adopted; do not add or remove them after seeing validation. Even satisfying
them supports strength in this named local pool, not a predicted Kaggle rating.

Passing validation permits a single frozen holdout evaluation, not immediate
promotion. Holdout remains **20000–20127**. A matched holdout against the same
incumbent requires 1,024 games per policy, 2,048 total. Freeze the artifact and
decision rule first. If validation or holdout informs code changes, retire the
inspected split and name an untouched replacement; never relabel reused data.

## Comparison implementation findings

`phase2_compare.py` already preserves seat/seed/policy dependence, rejects
duplicates and incomplete Cartesian panels, verifies frozen source bytes,
checks opponent and environment identities, and validates the full panel before
selecting pool weights. Its tests cover missing results, paired cash alignment
and hidden mismatches in otherwise unselected opponents. Those protections
should be retained.

The fresh-validation wrapper must additionally enforce the following, rather
than relying only on generic pairwise equality:

- The exact four opponents, **3000–3063**, two seats and 512 unique games per
  policy. Two equally truncated panels can otherwise look complete for their
  smaller inferred seed set.
- `resolved_seed == seed` on every row. The generic comparator currently checks
  only that the two policies' resolved seeds agree.
- The approved effective configuration, exact frozen policy hashes and current
  packaging evidence. Pairwise matching alone permits both policies to share
  the same incorrect configuration or wrong requested identities.
- Packaging success tied to actual assertions and the new hash. The older
  reporter's hard-coded `trajectory_actions_compared == 2876` and
  `fresh_processes == 2` are evidence for its old check, not a reusable proof of
  a newly refactored artifact's correctness.
- Runtime quantiles labeled as episode-level summaries of per-game action
  quantiles, unless raw action timings are retained. Stderr turns are not exact
  fallback counts when diagnostics have multiple causes. Zero stderr does
  establish no observed fallback that logs through that channel.

The official interpreter's shared weed/shop RNG remains consequential: matched
seeds are full-policy interventions, not fixed demand paths. No reviewed
validation claim should rely on private opponent state or future draws; replay
accounting can use them only as explicitly offline diagnosis. Live scoring,
hosted execution and rating remain separate evidence requirements.

## Confirmation wrapper delivered

`scripts/phase3_confirmation.py` implements the explicit protocol schema for
both validation and holdout. It retains the inherited gates and adds the named
COK 40% floor and an **equal-four** lower 95% score bound above 50%. The latter
is distinct from the stronger challenge-only lower-bound recommendation above;
the wrapper does not silently enforce that additional recommendation. The
frozen protocol JSON is the source of the final adopted thresholds and hashes.

The wrapper accepts extra preregistration metadata, rejects weakened inherited
thresholds, validates outcomes before statistical reporting, and verifies frozen
source bytes through the existing comparator. Its aggregate verdict is named
`statistical_runtime_gates_pass` to avoid implying that it independently proves
packaging or hosted compatibility. Focused confirmation tests and existing
comparison tests pass together: **21 tests**, using synthetic temporary evidence
without accessing reserved games.

## Explicit phase-four retention gates

The same wrapper now accepts `gate_set: "phase4"`; an absent selector retains
the phase-three behavior. This implements the changed incumbent and research
question in `phase4-protocol.md`, without retroactively qualifying v8 under the
old protocol. The phase-four gate schema replaces `anchor_min_delta` with
`anchor_min_score: 0.95`, `anchor_delta_lower_min: -0.05` and
`equal_four_min_delta: 0.03`. It raises `cok_min_score` to at least `0.5` and
retains all other shared gate fields. Stricter declarations are allowed; weaker
ones and unknown gate selectors are rejected.

Anchor retention and the three-point equal-four gain are inclusive score
thresholds. The lower paired anchor bound must be strictly above minus five
points, and the lower paired equal-four improvement bound strictly above zero.
Challenge improvement remains strictly positive, its score at least 50%, and
the equal-four score lower bound strictly above 50%. Independent anchor family
floors, zero candidate errors and maximum action time strictly below 0.5 seconds
remain mandatory. The report records the selector, and validation and holdout
use the same declared gate set.

The confirmation and comparator suite now passes **31 tests**. New synthetic
cases cover incumbent anchor saturation, retention failure, inclusive gain and
COK boundaries, strict confidence-bound comparisons, weakened declarations and
unknown selectors. The ceiling case passes the new retention criteria and still
fails the unchanged phase-three anchor-improvement criteria. No new games or
reserved seeds were read for these checks.
