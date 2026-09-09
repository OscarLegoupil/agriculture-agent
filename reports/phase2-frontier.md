# Competitive frontier, 9 September 2026

The first phase's anchor pool understates the current challenge. The unchanged
v7 release lost all eight games to COK V10 and seven of eight to Seyam V21 on
the four historical audit seeds. These are local executable comparisons, not
leaderboard estimates. Their results qualify both implementations for the
challenge pool while preserving the original anchor pool and its weights.

## Executable rules and hosted evidence

The latest upstream commit touching Kaggriculture was
[`28b6d8af3ce73926b3d0fda1410c1ddd8384ab8c`](https://github.com/Kaggle/kaggle-environments/commit/28b6d8af3ce73926b3d0fda1410c1ddd8384ab8c),
dated 15 August 2026. Downloading its interpreter, configuration, README and
AGENTS guide produced byte-identical files to the installed 1.32.7 package.
Interpreter SHA-256 is
`bc8a54879ef02c7ea64b8b333d6a976f0ea65c4949149d01f463f23bccee653e`;
configuration SHA-256 is
`a82c89c1a2315b93f39775d8e025471a01b738647c9772658368ee6b1b6f4867`.
The official configuration specifies 720 episode states and a one-second
action timeout. No environment upgrade was made.

The organizer's [balance announcement](https://www.kaggle.com/competitions/kaggriculture/discussion/735311)
identifies 1.32.7 as the egg/carrot/tomato scarcity update. Current source
equality supports local rules continuity; it cannot prove every hosted match
uses the same effective configuration.

Direct requests to the [evaluation page](https://www.kaggle.com/competitions/kaggriculture/overview/evaluation),
rules, and leaderboard returned no readable current content. Indexed
[participant observations](https://www.kaggle.com/competitions/kaggriculture/discussion/736219)
describe a dynamic rating, two active submissions, and a final Bradley–Terry
evaluation. These are explicitly participant reports, not independently
verified current platform parameters. Their fitted convergence curves should
not be used to predict our rating. Current hosted CPU/RAM, quota, rating and
account eligibility require authenticated verification; none is inferred from
another repository's account state.

## Reviewed challenge references

`scripts/fetch_challenge_references.py` reproduces the exact executable bytes
and retains repository licenses and notices in ignored local clones. It
records both the Git blob hash and Windows qualification-file hash in
[`challenge-reference-manifest.json`](challenge-reference-manifest.json).
The difference is CRLF line endings, not a policy modification.

| Reference | Pinned revision | Reviewed policy | Provenance limitation |
|---|---|---|---|
| [Seyamalam](https://github.com/Seyamalam/Kaggriculture) | `8b8c421eb10634c756583ce10c75189f50c83a72` | V21, public-state market recovery over public V18/C20 routes | Apache-2.0 attributed route source; repository's reported live success used older environment evidence |
| [COK-ZhangZiliang](https://github.com/COK-ZhangZiliang/Kaggriculture) | `7ef67eac458cd9ecd13786063e2e581fbe7403ec` | V10, public-shop route selection and execution recovery | Apache-2.0 public route lineage; stated target rating is not an achieved rating |

The two wrappers are separately maintained but share public route traditions.
They increase the difficulty of the pool without establishing two independent
production families. Neither is a strong independent crop-only agent. Their
embedded schedules come from public historic play; these are actual executable
wrappers that react to current observations, rather than a claim to execute
private leaderboard binaries.

Before execution, AST inspection and source review covered imports, top-level
operations, compressed payload use, entrypoints and market/recovery logic.
Imports were standard-library math, JSON, compression and copying utilities.
Compressed payloads decode into JSON data; no network, subprocess, filesystem,
dynamic code execution or external imports were found in either executable.
Only the opponent files were run, not repository setup scripts. No reference
source is redistributed in our submission or source snapshots.

## Qualification and diagnosis

Candidate: unchanged v7 artifact
`750f123073865347efd3b9c4b72022ff9923f4130c929ac76c1b0742374b09ee`.
Seeds: 0, 17, 42, 103, both seats. All are previously used development data.
Sixteen games qualified the opponents; eight additional reversed COK games
collected its realized-action telemetry. The reversed games reproduce the same
cash outcomes exactly after seat matching, and are not eight extra independent
match observations. All 24 executions finished DONE/DONE. Manifests include
configuration, executable hashes, runtime and selected replay paths.

| Opponent | v7 wins | Mean v7 cash | Mean opponent cash | Mean cash gap |
|---|---:|---:|---:|---:|
| Seyam V21 | 1/8 | 72,202.13 | 97,419.50 | −25,217.38 |
| COK V10 | 0/8 | 61,820.25 | 95,964.50 | −34,144.25 |

Eight games cannot estimate a stable win rate. The large deficits are enough
to reject the hypothesis that the original anchors cover the competitive
frontier. Detailed records are in
[`phase2-frontier-summary.json`](results/phase2-frontier-summary.json) and the
two corresponding compressed result archives.

In seed 0 with v7 in seat 0, COK has 19 strawberries by day 10, compared with
v7's one. By day 15 it maintains 38 strawberries, 17 wheat, 10 cows and four
sheep across three quadrants. V7 has six strawberries, 12 melons, eight wheat,
four cows, six sheep and eight geese across two quadrants. V7 leads cash at
day 15 (26,599 versus 19,980) but loses 57,496 to 97,429. The earliest visible
structural divergence is committing the second crop cycle to strawberries
before their maturation window closes, rather than accumulating cash and
maintaining a large goose/melon allocation. This is a causal hypothesis, not
proof from a single trajectory.

Across the eight matched COK games:

| Realized measure per game | v7 | COK |
|---|---:|---:|
| Strawberry sale income | 8,389.13 | 48,399.50 |
| Successful watering actions | 472.88 | 909.00 |
| Successful DROP actions | 170.75 | 8.88 |
| Successful PICKUP actions | 192.25 | 121.25 |
| Idle PASS actions | 676.88 | 558.63 |
| Labor expense | 5,133.38 | 5,977.00 |

COK supports nearly twice the watering with only 16% higher labor spending.
Frequent v7 deliveries compete with crop service; normal nightly automatic
delivery provides an alternative for products whose immediate sale is not
valuable. This does not imply all deliveries should disappear: worker carrying
capacity, storage overflow, immediate capital needs, shared-price capture and
the final day's missing automatic delivery still matter. COK itself has failed
pickups, so its execution should inform diagnostics rather than be assumed
correct.

## Ranked next experiments

| Priority and hypothesis | Expected impact and uncertainty | Smallest informative experiment |
|---|---|---|
| 1. Joint second-cycle crop expansion and inventory routing | Potentially tens of thousands in recurring revenue; high interaction risk | Day-5-to-15 strawberry commitment, three quadrants and inventory-aware delivery; compare against each component alone on known seeds |
| 2. Value worker service by obligations through the next reset | Could release hundreds of transport/idle turns; medium engineering effort | Raise delivery threshold only when existing capacity covers expected collection, retain capital and endgame overrides; measure harvested/sold units and maintenance losses |
| 3. Reallocate goose labor and land to premium production | Eight geese consume feed, care and collection while stronger references keep larger dairy herds; market-dependent | Matched fewer-geese/different-herd intervention with the same crop and labor schedule, not passive-opponent cash maximization |
| 4. Time premium sales after town consumption and against observable supply | High price sensitivity but uncertain incremental gain after production repair | Keep physical actions fixed, alter only timing/quantity; preserve ten-order and working-capital constraints |
| 5. Stage labor and expansion from actual workload | References achieve much larger acreage with similar hires; schedule/geometry may dominate headcount | A labor frontier conditioned on mature obligations, recording water/harvest service, travel, cash runway and terminal repayments |

Recent [public discussion](https://www.kaggle.com/competitions/kaggriculture/discussion/739273)
describes substantial success from public replay schedules. That makes
high-quality fixed routes a necessary stress test, not evidence that copying a
layout will generalize. Our next candidate should earn its improvement against
both the frozen anchors and these qualified challenges, with matched incumbent
runs and fresh validation after development.
