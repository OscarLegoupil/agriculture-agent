# Phase 3 evidence and implementation review

Review checkpoint: 2026-09-09, before a release candidate is selected. The opening
improvement is supported on its recorded development panel. It does not yet
establish generalization, a competitive promotion, or live leaderboard strength.
No additional games were run for this review.

## Verified performance claim

Recomputed all 30 opponent groups in the seven archives indexed by
`reports/results/phase3-development.json` at the review checkpoint. Uncompressed
archive hashes, executable snapshot hashes, game counts, wins and mean cash gaps
agree with the index. All checked games completed normally.

The strongest six-seed opening claim refers to this exact executable:

`febe9c76051a11e9ea7700e2d4701722e98274c51c50874ad03e1088b9398d4b`

| Opponent | Wins / games | Mean cash gap |
|---|---:|---:|
| Seyam | 12 / 12 | +11,288.50 |
| COK | 5 / 12 | -1,421.58 |

Both seats appear exactly once for each seed 0, 5, 11, 17, 42 and 2001. The two
screen files do not duplicate scenarios for this candidate. The statement in
`phase3-opening.md` is accurate, including its warning about small panels and
dependent seats. The 14-cow result uses a different executable and a smaller
panel; it must not be combined with these totals.

## Archival defects corrected during review

The initial collector rejected two manifest formats already produced by the
benchmark tools: a direct candidate/hash manifest and a generic benchmark whose
executed candidate is a frozen path while its source hash is keyed by the
submitted path. Windows path separators made path matching more fragile. It
also wrote archives before validating subsequent inputs and could overwrite
different experiments sharing a basename.

The corrected `candidate_identity` resolves these recorded relationships
explicitly and normalizes separators. The collector now validates every input,
source snapshot and destination collision before writing evidence. Five tests
in `tests/eval/test_phase3_report_review.py` pass using synthetic temporary
workspaces: the three manifest schemas, failure without partial publication,
and rejection of conflicting basenames. These corrections affect evidence
handling; they do not change candidate behavior or game results.

## Data boundaries and causal interpretation

A seed-field scan of 29 available phase-3 raw and archived records found only
0, 5, 11, 17, 42, 2000 and 2001 at this checkpoint. No reserved validation
3000–3063 or holdout 20000–20127 scenarios appeared. Previously inspected
phase-2 validation 2000–2063 is correctly treated as development data now.
The subsequently declared 2000–2015 confirmation panel is also development,
regardless of its larger size.

The official end-of-day sequence consumes weed randomness before drawing shops.
Weed draws depend on empty tiles, so changed planting can change the later shop
sequence even with identical seeds. Matched seeds remain useful full-policy
comparisons, but do not hold exogenous demand or opponent responses fixed.
The opening report correctly describes fertilizer expense changes as observed
whole-policy effects. Directly interpreting those differences as the isolated
value of fertilizer would be incorrect.

## Information use and remaining release checks

The reviewed opening and herd builders modify the frozen `0098` candidate. The
market model uses observable assets and crop ages, current town shops, public
market inventory and prices, plus the player's own private inventory. Future
shops enter as an expectation, not realized draws. No reviewed decision path
uses seed identity, private opponent inventory, benchmark files or leaderboard
identity. External references remain benchmark opponents rather than imports
of the candidate. This is a source review, not a proof covering future changes.

The exploratory collector now uses the shared error-aware match scorer and
records missing cash separately; an additional regression test covers a failed
episode with an absent reward. Its completion flag and duplicate checks do not
independently prove that a declared panel is complete; promotion must verify
the frozen protocol's full scenario set.

Before promotion, the exact selected artifact still needs fresh matched
validation against both unchanged pools, seed-cluster uncertainty for paired
improvements, release packaging/parity/reset checks, and runtime headroom.
Seyam and COK share implementation lineage, so their games cannot establish
coverage of two independent strategy families. The current COK deficit and
the absence of live evidence remain material limitations. The incumbent release
must remain available until the complete promotion criteria are satisfied.
