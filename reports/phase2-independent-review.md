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

## Subsequent bounded animal-service experiment

A separate implementation experiment tested finite-horizon feed/care decisions
on unchanged v7. `scripts/phase2_animal_service.py --probe` checks 1,980 small
state transitions against the official animal refresh, including missed feeds,
production-eve care consumption and care banked after production. The model
uses current quotes only and consistently applies admitted feed demand to
purchases and sale reserves.

The candidate is
`92512ba2f62f7ff6f58634dfae7112b00cdd2f3e3161abc3dd7a86d293935707`.
It was rejected after 16 historical development games (17 and 103, both seats,
four opponents):

| Opponent | Incumbent wins | Service-DP wins | Incumbent mean gap | Service-DP mean gap |
|---|---:|---:|---:|---:|
| lonespear | 4/4 | 2/4 | 13,891.50 | −1,194.75 |
| GzmCR | 1/4 | 1/4 | −8,471.00 | −14,308.50 |
| Seyam | 1/4 | 0/4 | −19,602.50 | −18,072.25 |
| COK | 0/4 | 0/4 | −33,350.25 | −64,560.50 |

The intervention reduced feeding/care work without reliable competitive gain.
Against COK, candidate cash rose by 20,715.75 while the cash gap worsened by
31,210.25: a direct counterexample to promoting on own cash. These are
whole-policy interventions including opponent responses and changed shop
paths. All executions finished normally with zero stderr and maximum observed
action time 76.5 ms.

The transition model is exact for its small animal state; its economic value
is not. It assumes immediate harvest and constant current prices, charges a
small action cost without field travel, and credits fertilizer from the final
refresh that v7's current final-day controller does not collect. Asset
abandonment and daily replanning also change recovery requirements. These
limitations and the negative screen rule out promotion. The code remains
isolated as a reproducible failed experiment; no deployed policy was changed.
Detailed records are in `results/phase2-animal-service.json.gz` and
`results/phase2-animal-service-summary.json`.

## Review of the liquidity/model/expansion challenger

The subsequent experimental champion is
`0098d9e4f77e2420cb4a09abd47e49f5160009cd0818ae37a793bc3e419ffc4b`,
produced by `phase2_correctness.build("liquidity_model_expand")`. Regenerating
it during review produces byte-identical source to the content-addressed
artifact named in `data/raw/phase2-best-path.txt`. Its 710-line executable
uses only standard-library imports. All referenced parameter keys exist;
configuration fallbacks cover shed capacity and market-order limits. The
forecast reads current public market inventories, public crop/animal ages and
held production, and already unlocked shops. It reads no random seed, future
realized state, external files or private opponent inventory. There are no
mutable episode globals beyond fixed initialization parameters.

The implemented changes remove an hour-23 planting opportunity that cannot be
watered that day, align fertilizer purchase targets and reserves, release fertilizer
working capital when cash is low, permit affordable partial feed orders, and
combine a public-inventory price scenario with larger production capacity.
No fatal accounting or deployment-boundary defect was identified in those
changes. The candidate still inherits heuristic labor, care, transport and
terminal task values; this review is not a proof of economic optimality.

The new forecast is a scenario, not an exact forward simulator. It assumes
future servicing and immediate sale of currently held output, omits future
replanting and additional herds, approximates care, and does not model crop
decay before the hypothetical delivery. Future shop demand is an expectation
over possible shops, which is legitimate but uncertain. Testing the exact
price curve and empty-farm transitions does not validate production-scenario
ranking. The observed competitive results, rather than curve agreement alone,
must justify its use.

The 24 completed anchor development games for this hash record zero failed
work and stderr, with maximum observed action duration 88.8 ms. These are
local timing observations, not hosted certification. The six-seed challenge
record supplied for review remains 7/12 against Seyam and 0/12 against COK;
the 29.2% equal-weight challenge score fails the stated 50% requirement. The
incumbent remains the release, and these development results cannot be
presented as validation or promotion.

The new `phase2_compare.py` addresses the main statistical findings above:
identical complete scenario sets, exactly one row per seat, common bootstrap
seed blocks containing both policies, fixed CLI pool weights, completed-run
markers, executable hashes, interpreter/dependency-lock identity, and matching
effective configurations. Six comparison/game-contract tests passed during
this review. Benchmark records now include realized shop sequences and check
source hashes after the run.

One concrete remaining reporting defect was reproduced: a candidate ERROR
with `cash=None` correctly receives a zero match score but causes cash-gap
subtraction to raise `TypeError`. Error-containing panels should produce an
explicit failed gate and defined missing-cash treatment, not an unusable
report. Opponent errors should also be counted separately. Freeze the
challenge identities/weights in the protocol text before validation, and
include compared artifact identities in the saved comparison report so it
remains interpretable apart from its command history.

## Pre-validation reporting fixes

The selection protocol and expanded challenger were frozen at
`9b73672102a64d6818b9c895838360d5e15ebc89`. Subsequent reporting changes do not
inspect partial validation results or alter policy behavior.

Nullable rewards now remain in the match-score denominator while missing or
non-finite rewards are excluded from cash summaries with explicit valid and
missing counts. Paired cash changes use only complete observations for the
same scenario. Empty cash summaries return JSON null. Candidate, opponent,
incumbent and incumbent-opponent execution errors are counted separately,
including both-error episodes. The previously reproduced TypeError is fixed.

`compare_manifests(old, new, weights)` now provides the same integrity checks
to the CLI and programmatic reporting. It requires completed manifests before
examining episodes, validates the full scenario panel and every opponent's
hash before filtering to an anchor/challenge subset, checks environment and
dependency provenance, and verifies each candidate's declared source hash
against both its frozen executable and decompressed source snapshot. Every
episode must name that verified frozen candidate. Changed opponents outside
the requested pool cannot be silently hidden by filtering.

The returned report includes both candidate identities, revisions, source and
snapshot paths, all opponent hashes, full-panel dimensions, and a digest of
scenario configurations. Six targeted tests pass, covering missing rewards,
error status seat semantics, incomplete and duplicate scenarios, unselected
opponent mutations, dependency mismatch, and source/frozen/snapshot identity
failures. Frozen executables and snapshots must be available when re-running
this integrity-sensitive comparison; source snapshots alone do not silently
substitute for missing execution artifacts.
