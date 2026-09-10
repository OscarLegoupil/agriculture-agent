# Grown feed and crop-capacity interaction

More wheat improves the farm's wheat cash ledger, but displaces berry income and does not produce a consistent matchup gain. The plain higher-wheat policy improves COK on this small panel while losing two Seyam games. Combining wheat targets with additional land and crop capacity does not dominate the incumbent. None is promoted on these screens.

## Frozen comparisons

Each candidate plays the same four known development seeds, 3000, 3017, 3042 and 3063, both seats, against pinned COK and Seyam: sixteen games per candidate, 64 total across two complete panels. V8 (`64fe3239…`) supplies exact matching baseline records from its now-inspected validation panel. The reporting script verifies full declared coverage, source/snapshot hashes, opponent hashes, environment/dependencies and effective scenario configuration before comparisons. Draws count as half a win; none occur here. Four seed clusters are inadequate evidence for generalization, particularly after repeated development use.

The plain variants target one or 1.5 standing wheat tiles per placed animal from days 8–24, bounded to 7–28. They override normal planting rankings while below that target, subject to positive estimated finite-season value and existing cash/seed checks. They are production mixes, not optimized feed forecasts or guarantees of self-sufficiency. The expanded variants add the previously tested four-plot, 70-crop, 12-hand-capacity policy. Opening and terminal observation parity is preserved outside the override window; intervening trajectories can diverge.

| Candidate | COK wins / 8 | COK mean cash gap | Seyam wins / 8 | Seyam mean cash gap |
|---|---:|---:|---:|---:|
| Frozen v8 | 4 | -1,744.75 | 8 | +7,646.13 |
| Plain wheat target 1.0 | 4 | +1,525.50 | 6 | +6,072.75 |
| Plain wheat target 1.5 | 6 | +8,732.63 | 6 | +5,577.25 |
| Expanded wheat target 1.0 | 1 | -5,762.00 | 5 | -145.88 |
| Expanded wheat target 1.5 | 4 | -2,741.75 | 7 | +8,874.38 |

The plain 1.5 target changes COK's mean gap by +10,477.38 and Seyam's by -2,068.88, tying v8's overall 12/16 score. It merits a broader known-data family-tradeoff check; that is separate from promotion. Expanded 1.0 loses heavily. Expanded 1.5 remains below v8 overall, at 11/16.

Against the exact original 70-crop policy, whose screen was COK 3/8 and Seyam 2/8, expanded 1.0 changes scores to 1/8 and 5/8; expanded 1.5 changes them to 4/8 and 7/8. These interactions show that mix matters within additional capacity, but do not establish that adding land improves the plain feed policy. They must not be presented as additive component gains.

## Actual cash flows and displaced production

Wheat net cash below is **wheat sales minus all wheat purchases, including seeds**. It is a cash-ledger quantity, not crop profit: it excludes labor and land and does not assign an artificial sale to home-grown feed consumed by animals. Berry income is actual gross strawberry sales, not a quote-valued inventory estimate.

| Candidate | COK wheat net cash | COK berry income | Seyam wheat net cash | Seyam berry income |
|---|---:|---:|---:|---:|
| Frozen v8 | -5,070.75 | 28,293.38 | -5,730.13 | 44,262.25 |
| Plain 1.0 | -978.75 | 26,310.50 | -90.50 | 34,565.25 |
| Plain 1.5 | +967.63 | 24,744.63 | +3,408.63 | 30,285.75 |
| Expanded 1.0 | -1,394.50 | 31,201.13 | -1,201.50 | 36,133.75 |
| Expanded 1.5 | +1,228.13 | 27,799.25 | +2,186.25 | 34,101.63 |

Against Seyam, plain 1.5 improves wheat net receipts by 9,138.75 but loses 13,976.50 in berry income. The feed ledger improves without an overall matchup improvement. Against COK the same intervention improves wheat net by 6,038.38 while berry income falls 3,548.75. Those changes do not equal the whole cash-gap effect: animal income, other expenses, opponent responses and changed market/shop trajectories also contribute. No direct causal feed-savings claim follows from the gap alone.

Actual mean day-15 standing crops confirm that the mechanism changed the farm, rather than merely buying different seeds:

| Candidate | COK wheat / berries | Seyam wheat / berries |
|---|---:|---:|
| Frozen v8 | 6.75 / 42.75 | 7.00 / 42.63 |
| Plain 1.0 | 14.63 / 33.25 | 16.50 / 33.13 |
| Plain 1.5 | 18.88 / 28.75 | 22.25 / 25.75 |
| Expanded 1.0 | 17.13 / 47.25 | 17.50 / 46.13 |
| Expanded 1.5 | 23.88 / 38.13 | 25.00 / 38.88 |

Expanded 1.0 does retain more berry tiles, yet its COK result deteriorates. A productive-footprint target alone is not an economic plan. Full day-15 animal/crop compositions, actual hired-worker expense, movement and input purchases are retained per opponent in the summary.

### Did the expanded high-feed policy realize its intended mix?

No. Its target is based on currently placed animals, so four animals on day 8 request only seven wheat tiles. Later herd placement raises the target to 27. The policy does not remove existing berries to reserve future feed capacity. However, lack of eventual crop-budget space is not the whole explanation: by day 15 both matchups still have room below the 70-crop ceiling.

The following are means at the start of each day for expanded 1.5. Paired entries are **COK / Seyam**; target values come from the exact observed-animal rule, not a retrospectively optimized target.

| Day | Wheat target | Actual wheat | Actual berries | Remaining crop-budget slots | Owned plots |
|---|---:|---:|---:|---:|---:|
| 8 | 7.00 / 7.00 | 5.25 / 2.00 | 23.50 / 24.13 | 27.25 / 29.88 | 2 |
| 9 | 9.50 / 13.00 | 5.50 / 2.63 | 23.50 / 24.13 | 27.00 / 29.25 | 2 |
| 10 | 10.25 / 14.38 | 5.00 / 1.75 | 23.50 / 24.13 | 27.50 / 30.13 | 2 |
| 11 | 12.50 / 17.00 | 7.38 / 6.00 | 25.13 / 24.75 | 34.63 / 37.13 | 3 |
| 12 | 20.25 / 21.50 | 11.63 / 15.00 | 28.38 / 30.50 | 28.00 / 22.50 | 3 |
| 13 | 24.25 / 27.00 | 17.13 / 20.38 | 33.00 / 35.25 | 18.50 / 13.38 | 4 |
| 14 | 26.63 / 27.00 | 22.38 / 24.38 | 36.50 / 37.38 | 11.13 / 8.25 | 4 |
| 15 | 27.00 / 27.00 | 23.88 / 25.00 | 38.13 / 38.88 | 8.00 / 6.13 | 4 |

On days 9–10 there are at most one nonproductive owned tile on average despite nominal crop-budget space; opening melons and the existing farm occupy the two owned plots. By day 15, the upper bound on nonproductive owned tiles is 20.00 / 18.13, and the crop-budget headroom is 8.00 / 6.13. Thus the missing wheat cannot be blamed solely on berries filling the 70 slots. Clearing, seed availability, route assignment and commissioning speed remain constraints; these daily snapshots do not isolate their individual effects.

The intended 43 berries plus 27 wheat is never established by day 15. Wheat falls further after harvest: on day 17 it averages 17.88 / 19.50, while berries remain 38.13 / 38.88. The steady target does not guarantee timely replanting. This experiment evaluates a delayed and partly filled production mix, not a fully serviced 70-crop wheat/berry allocation. Its failure does not prove that such an executable allocation would be unprofitable. The summary now preserves all day-8–20 crop, target, land and headroom measurements for reproduction.

## Rejected premium-berry guard

A post-hoc analysis of the completed high-feed field suggested that the
high-feed policy fared poorly when the visible day-eight strawberry quote was
179. The resulting guard left the normal crop ranking in place whenever the
public quote was at least 1.49 times the base strawberry price, and otherwise
kept the frozen 1.5-wheat-per-animal override. This was deliberately a single
known-data screen, not an adaptive-policy search or validation result.

The frozen artifact `fe3826a191c0ffcf49db101edc1e2551c2174268e5a74fa0a79228d8ef93a33d`
completed the original 16-game panel with zero errors and zero stderr turns.
It won **3/8 COK** games with a mean cash gap of **-4,052.12**, versus v8's
4/8 and -1,744.75, while retaining 8/8 Seyam wins (mean gap +10,128.88).
The apparent quote split was therefore not a useful general decision rule on
the same development panel that generated it. The candidate is rejected and
will not receive a broader screen. The complete manifest is
`data/raw/phase4-premium-berry-guard.json`.

## Labor and reliability

| Candidate | COK labor / moves, mean | Seyam labor / moves, mean | Water deaths, COK / Seyam | Nonterminal escapes, COK / Seyam |
|---|---:|---:|---:|---:|
| Frozen v8 | 7,967.75 / 4,182.38 | 8,093.75 / 4,201.88 | 5 / 2 | 0 / 1 |
| Plain 1.0 | 7,967.75 / 4,161.63 | 8,093.75 / 4,188.13 | 5 / 5 | 0 / 1 |
| Plain 1.5 | 8,021.75 / 4,151.75 | 8,093.75 / 4,153.13 | 6 / 9 | 2 / 0 |
| Expanded 1.0 | 7,936.00 / 4,157.63 | 8,224.00 / 4,159.88 | 6 / 6 | 1 / 1 |
| Expanded 1.5 | 7,954.00 / 4,117.13 | 8,224.00 / 4,130.38 | 5 / 4 | 3 / 4 |

Loss counts are summed over each eight-game matchup. Terminal escapes are stored separately and are not assumed optimal abandonment. Extra production can displace animal service even when movement decreases. All 64 new games completed normally with zero candidate stderr; the largest decision duration was 265.702 ms. These local measurements do not establish hosted resource compliance or zero timing-dependent fallback inside the unchanged assignment solver.

## Reproducibility and decision

Frozen source identities:

| Variant | SHA-256 |
|---|---|
| Plain 1.0 | `36e95469bb83dba2c73622ac0c66dd24a4d8611ccea0ce789b95ae6ee47ea642` |
| Plain 1.5 | `e15a78e4eed4929480c4225e74ebd3f8abb3aee38e2b459832ae8a7b2de63265` |
| Expanded 1.0 | `f005ddbbcdbe34841965106ac7906fd5ed372ca3d35f5bfbbf8b126bd32cb7d3` |
| Expanded 1.5 | `909b5a1f8e9b6dbec3998f28a10a8b7f95fbd43175cc03be9bf5f58d0a78c5b1` |

```powershell
python scripts/phase4_mix_report.py
ruff check scripts/phase4_mix_report.py
```

The command runs no games and rejects incomplete panels. [Matched summary and uncertainty](results/phase4-feed-mix-summary.json), [plain screen archive](results/phase4-feed-mix.json.gz), and [interaction archive](results/phase4-production-interaction.json.gz) preserve the complete evidence. The summary includes both v8 comparisons and exact 70-crop comparisons for the interactions.

The expanded variants are not selected. The plain 1.5 policy proceeds only to the separately declared 128-game known-data check on seeds 3000–3031, retaining both challenge opponents and both seats. Fresh validation and holdout remain unopened for it. Its COK improvement is currently a hypothesis requiring that broader check, not an established competitive result.
