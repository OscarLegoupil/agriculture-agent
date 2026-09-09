# Independent presentation and feed-cohort review

Reviewed the in-progress README, frozen v8 source/build path, saved phase-three validation and packaging evidence, and `scripts/phase4_feed_mix.py`. No games were run and no policy or README edits were made by this review. The feed screen was not used for this source review.

## Accepted evidence

The README's strongest numerical claim is supported. Independently counting the complete compressed manifests gives 271/512 wins for the previous experimental champion (`0098d9e4…`) and 414/512 for v8 (`64fe3239…`): 52.9297% and 80.8594%. The saved seed-cluster bootstrap reports +27.9297 percentage points, interval [23.8281, 32.0313], and v8's score interval [77.5391%, 83.9844%]. Both policies, seats and all opponents remain grouped by seed. The exact per-opponent counts are:

| Opponent | Previous | v8 | v8 mean cash gap |
|---|---:|---:|---:|
| lonespear | 126/128 | 128/128 | +43,803.88 |
| GzmCR | 117/128 | 128/128 | +41,180.38 |
| Seyam | 26/128 | 117/128 | +15,460.80 |
| COK | 2/128 | 41/128 | -4,528.29 |

All 1,024 archived games are DONE/DONE with zero candidate stderr. The maximum v8 action duration is 113.925 ms. The README explicitly discloses the failed COK floor, unopened final holdout, known status of inspected validation seeds, related challenge-route ancestry, and absence of live rating evidence. These qualifications are necessary and correctly accompany the headline.

The LF-normalized current policy source and standalone v8 executable both hash to `64fe323936dc9494add413eb956b0294658a88efe28572332c94676c68a09325`. The packaging script normalizes line endings deterministically and defaults to the v8 directory. The saved packaging record supports 2,876 trajectory action comparisons, 60 isolated observations, two fresh processes and 24,801,280-byte Windows peak RSS. Corrected Linux CI records the same v8 hash and 23,506,944-byte current-image RSS. These are appropriately presented as local measurements rather than hosted guarantees.

Every relative Markdown link in the inspected README resolves locally. Both current validation figure sidecars match the exact summary and incumbent/challenger manifest hashes. The screenshot is explicitly labeled historical v7, rather than being presented as a v8 replay. Apparent mojibake from default PowerShell decoding is not in the UTF-8 README bytes.

## Presentation corrections to make

1. The smoke test now executes **both v7 and v8 in both seats**, four games. Describing it as one frozen artifact in both seats understates the actual command.
2. `search_production.py` is explicitly a **historical v7** screen. Label that command accordingly rather than suggesting it searches the current v8 production class. Current validation figure reproduction should point to `phase3_figures.py` rather than only the historical `figures.py` command.
3. Prefer “current experimental policy source” to an unqualified “deployed policy” when distinguishing source/build defaults from the still-qualified v7 rollback. No live deployment is established. The submission command correctly names v7; an explicit sentence explaining that choice would remove ambiguity after the v8 headline.

These are reproducibility and terminology corrections, not reasons to retract the measured validation improvement.

## Feed-cohort candidate: legal scope, approximate economics

The candidate starts from the exact frozen v8 snapshot. It changes only crop selection inside the existing planting loop, on days 8–24 when placed animals are observed. It targets one or 1.5 standing wheat tiles per observed animal, bounded to 7–28. Inputs are current public animals, own current/planned crops, the existing observation-derived wheat forecast, prices and the current day. There is no seed identity, private opponent inventory, future realized randomness or external route lookup in the inserted logic.

The gate uses the existing finite-season `crop_value` estimate with annual fertilizer disabled. Days 25 onward receive no new override; the earlier opening is unchanged. The existing code still requires available seeds or budgeted seed purchases and suitable planting space. The retained 30 opening/terminal observations per variant support action parity on those same states, not identical trajectories after the middle-game intervention.

The experiment is a forced production mix, not a new economic optimizer. It raises wheat's ranking above every alternative until its target is reached. The protocol's word “compete” should therefore be replaced with “override the normal ranking while below the target, subject to positive estimated value.” That value uses the raw forecast wheat quote, whereas normal crop ranking applies an own-cohort saturation adjustment. Positive estimated value is not proof of marginal superiority to berries or of executable repayment.

The target counts standing crops equally regardless of remaining age/yield, and excludes animals purchased but not yet placed. It does not calculate current feed deficits or infer guaranteed self-sufficiency. The one/1.5 ratios are tile targets, not fractions of feed grown. The five-day cutoff is conservative calendar intent, but seed purchase, clearing, travel and delayed planting can shorten the actual production window; the inherited value model does not model those commissioning delays exactly.

The existing selling policy may also sell grown wheat and later buy feed. Evaluation therefore needs actual wheat harvests, purchases, sales, net feed expenditure, production displaced and service losses. A lower purchase count alone does not prove a stronger policy. More wheat also changes market supply and crop occupancy, potentially changing the seeded shop path. Matched whole-policy outcomes remain valid; claims that a cash difference is caused solely by feed-cost savings would not be.

No hidden-state or source/artifact inconsistency was found in this candidate. The stated causal and finite-calendar limitations should remain visible when interpreting its screen.
