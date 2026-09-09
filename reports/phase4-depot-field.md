# Banked depot obligations do not improve the broader field

Reject the banked-depot candidate for selection: it wins **79/128** challenge
games versus v8's **80/128** on the exact same known scenarios. The equal-weight
change is **−0.78 percentage points**, with a paired-seed 95% interval of
**[−10.16, +10.16] points**. This does not establish improvement. COK score and
the downside cash gap both worsen, despite retaining strong Seyam results.

| Opponent | V8 wins | Depot wins | Score change (95% paired CI), points | Mean cash gap, v8 → depot | Median gap, v8 → depot | Tenth-percentile gap, v8 → depot |
| --- | ---: | ---: | --- | ---: | ---: | ---: |
| COK | 21/64 | 19/64 | −3.12 [−17.19, +10.94] | −4,732 → −5,909 | −5,981 → −8,588 | −12,328 → −17,405 |
| Seyam | 59/64 | 60/64 | +1.56 [−9.38, +12.50] | +16,609 → +18,076 | +15,973 → +16,446 | +3,250 → +3,383 |

The mean paired cash-gap change is −1,176 against COK and +1,468 against
Seyam. Depot's pooled challenge score is 61.72%, with a seed-bootstrap score
interval [55.47%, 68.75%]; that absolute score does not supersede its failed
paired improvement or its 29.69% COK score. No anchor games were included, so
this experiment cannot establish anchor retention or equal-four qualification.

## Scope and identity checks

The comparison uses all **128 completed depot games**: seeds 3000–3031, both
seats, against the same two pinned challenge executables. The incumbent panel
is the exact Cartesian subset of the completed 512-game v8 validation manifest.
No rows are dropped from the requested scope. These seeds are now development
data, and the candidate was selected after earlier screening. This is neither
fresh validation nor an unopened holdout.

- Incumbent: `64fe323936dc9494add413eb956b0294658a88efe28572332c94676c68a09325`.
- Depot: `ee412dabf71824ebf32c870b021bc7ae0a3cc35d231f142c8c0fc8550d09a6ba`.
- Inputs: `data/raw/phase3-validation-challenger.json` and
  `data/raw/phase4-depot-field.json`.
- Output: `reports/results/phase4-depot-field-summary.json`, including input
  file hashes, verified source identities, opponent hashes, full scenario
  scope, configuration hash and effective dependency/interpreter identities.

The comparator verifies source bytes, completeness, opponent identities,
environment/interpreter/dependencies, matched configurations and resolved seeds.
The uncertainty calculation resamples 32 complete seeds 10,000 times using
RNG 20260910, preserving both seats, both opponents and both policies in each
cluster. Draws count as half a win. These intervals describe seed variation;
they do not account for adaptive candidate selection or incomplete opponent
coverage. Seyam and COK share public route ancestry and are not substitutes for
independent anchor families. Interpreter randomness may respond to changed
actions, so paired seeds do not guarantee identical realized shop paths.

All 128 candidate games and their opponents completed normally; candidate
stderr-turn and reported failed-work counts are zero. Candidate maximum action
time was **91.393 ms**. The 95th percentile across each game's action-p99 was
4.256 ms; this is not a pooled action-p99. The incumbent maximum was 99.050 ms.
Timing differences are observational across benchmark runs, not controlled
evidence of a speed improvement.

To reproduce the statistical comparison, load both input manifests, filter
the incumbent episodes to the two challenge paths and `3000 <= seed < 3032`,
then call `scripts.phase2_compare.compare_manifests` with equal weights of 0.5.
Do not filter either policy by outcome. The saved summary records the full
filter and file hashes so this scope cannot be confused with the original
four-opponent validation panel. Keep v8 as the experimental incumbent; this
candidate does not justify consuming fresh validation seeds.
