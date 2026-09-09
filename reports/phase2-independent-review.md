# Independent evaluation review

Reviewed 9 September 2026, before second-cycle validation. This review covers
the incumbent, challenge source boundaries, qualification evidence, protocol,
and early experimental builders. It is not approval of a final candidate;
the selected executable and final matched comparison require another review.

## Verified foundations

- The branch starts from `48f576f8d781785b90639d2072fd484acab8fd00` through
  `93e1395546b2c3ed23449d6cdc030b43afdb7fb1`. The v7 artifact is byte-identical
  to the former commit and retains SHA-256
  `750f123073865347efd3b9c4b72022ff9923f4130c929ac76c1b0742374b09ee`.
- Experimental builders read that immutable artifact, assert its hash, perform
  count-checked source transformations, write content-addressed files and
  preserve compressed candidate snapshots. The deployed source has not been
  replaced by an unverified experiment.
- The new protocol correctly retires the original holdout to known data. No
  episode in the current committed/result-directory archives uses validation
  2000–2063 or holdout 20000–20127 at this review checkpoint.
- Qualification has 16 distinct incumbent games. The eight reverse COK games
  reproduce every final cash pair exactly after swapping seats; they add
  opponent telemetry, not independent outcomes.
- Scores of 0/8 against COK and 1/8 against Seyam establish a substantial
  challenge gap. They do not establish either opponent's live rating, rank or
  a precise incumbent win probability.

## Material requirements before selection

### A paired improvement report is still required

The first-cycle `summarize_benchmark.py` reports an absolute one-candidate
score interval and the old promotion rule. It cannot establish the second
cycle's five-percentage-point gain and positive lower bound on improvement.
The new comparator must join exactly one candidate and one incumbent result
for every opponent version, seed and seat, then resample complete seed blocks
containing both policies and every declared opponent. Confidence intervals
from two separately bootstrapped scores are not a paired-difference interval.

Require identical scenario key sets, candidate hashes, opponent hashes and
environment versions/configurations. The old summary computes an intersection
of opponent seed sets; a missing scenario can silently disappear. That is
acceptable only as an explicitly incomplete exploratory report, never a
promotion report. Duplicate seat rows and missing games should fail closed.
Report opponent errors independently even when they correctly count as wins.

The challenge membership and weights are not yet frozen in the protocol.
Freeze them before validation and name the public-route lineage shared by
the new references. Keep anchor scores separate and unchanged. Do not average
an increasing number of variants into an apparent independent-opponent gain.

### Matching seeds does not fix realized shop paths

The official `_end_of_day` creates one RNG from seed and day, calls
`_spawn_weeds` on both farms, then draws the next shop. `_spawn_weeds` consumes
a random number only for empty tiles. Therefore policy-dependent occupancy
changes the number of draws and can change future shops under the same initial
seed. This affects both causal diagnosis and seat comparisons.

Seed-paired whole-policy comparisons remain valid experiments in the official
environment. Their treatment effect includes endogenous changes to the random
stream and the opponent's response. They must not be described as comparisons
under identical realized future demand. Save observed shop sequences alongside
the seed and effective configuration. Any intervention that forces a common
future shop path is a modified-environment diagnostic and must remain separate
from reported deployable performance.

### Nightly delivery requires aggregate storage accounting

The `nightly` intervention suppresses ordinary low-load returns unless cash
is below 3,000, current total stock reaches 75, or it is the terminal day.
Current stock includes carried quantities in the incumbent, but the heuristic
does not reserve the remaining day's future collections against the common
100-unit shed or rank products that compete for the last available spaces.
It is a screening intervention, not a proved storage-safe controller.

The interpreter's `_drop_inventories_to_shed` processes workers in index order,
then each inventory's insertion order. It deletes excess goods without an
economic priority. Test multiple workers delivering more than remaining shed
capacity, combined feed/fertilizer/product inventories, and the effect of
market sales occurring before automatic delivery. Check overflow by product
and, where possible, foregone sale value. A larger farm can expose failure
modes absent from a compact-farm screen. The final day has no automatic
delivery and needs its existing explicit return/sale logic.

## External reference boundaries

AST and source inspection of pinned COK and Seyam executables found no access
to environment seeds, future realized randomness, episode/submission identity,
filesystem, network or interpreter internals. Their `private` access is the
current agent's observation-private shed, seeds and carried inventory.
Opponent features come from public farms, money and market/town observations.
The literal `seed` in Seyam's economics denotes seed purchase cost, not the
environment RNG seed.

Lookahead references to `_ACTIONS[future]` and embedded expert schedules are
precomputed policy instructions derived from historical public play, not
reads of the current episode's future. Some selectors deliberately recognize
public farm signatures, which is observable behavior rather than unavailable
leaderboard identity. This review found no information-boundary violation;
current competition legal terms still require the account's ordinary
eligibility and rules checks before hosted submission.

The references remain isolated under ignored `data/raw`. Their original
Apache-2.0 notices and upstream licenses are retained. No external source is
included in our deployed policy. The fetch script verifies both canonical Git
blob hashes and exact CRLF executable hashes from qualification; this avoids
a Windows/Linux newline difference masquerading as a different policy.

The qualification result manifests locate the pins through the separate
challenge-reference manifest. For release evaluation, include these pins
directly or explicitly digest that manifest. Opponent source files should be
frozen or checked again after long experiments: the current harness freezes
the candidate but reads opponent paths throughout the run.

## Interpretation limits and final review checklist

Per-game action maxima and p99 summaries are useful, but do not constitute a
pooled per-turn runtime distribution. Report them with those exact labels.
Benchmark logs detect explicit stderr, not silently swallowed external-policy
exceptions. DONE/DONE is successful execution status, not proof that every
requested action succeeded. The existing realized-action telemetry provides
the needed additional distinction.

Before claiming promotion, inspect the frozen final source and artifact,
validate full matched scenario coverage, confirm the predeclared gates and
shop-path caveat, run packaging/state-reset/resource checks, and preserve a
single untouched holdout. A high score on this named local pool remains
separate from live leaderboard evidence and uncertainty about opponent
coverage.
