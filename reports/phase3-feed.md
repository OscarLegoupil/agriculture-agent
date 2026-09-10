# Prospective feed cohorts

The intervention reduced purchased feed but displaced more valuable recurring production. It is rejected for promotion: the corrected candidate lost mean cash gap against both opponents while preserving the same six wins in eight development games. These are screening results on two known seeds, not validation or a leaderboard estimate.

## Intervention and accounting correction

The frozen base is `startup_fert_reserve10`, SHA-256 `febe9c76051a11e9ea7700e2d4701722e98274c51c50874ad03e1088b9398d4b`. The initial seven wheat and twelve melon cohort is preserved. From day 8, an observed-herd feed deficit over at most five days admits additional wheat only when its estimated replacement value exceeds other crops. Owned animals awaiting placement count as obligations. Existing wheat ages/yields and shed wheat reduce the prospective deficit; terminal days stop admission. The model is a small heuristic, not an exact schedule or a future-state rollout.

The original eight-game pilot (`a8b3342e3e8d54fd16dbb5367627cbaf9b20330a4ed63df3058cce365232087d`) valued mature four-unit wheat even when the controller's shortage rule would harvest at age two. That inconsistency was detected before promotion. Its immutable output remains `data/raw/phase3-feed.json`, reproducible with `--valuation maturity`. On four already recorded incumbent COK trajectories, the optimistic branch made 7, 2, 31 and 31 early-harvest overrides; correcting valuation changed 1, 1, 2 and 2 action dictionaries. These are off-policy observed-state probes; they do not measure causal match improvements.

The explicitly authorized correctness recheck used eight additional games and a distinct artifact, `248d52253859e7af423296cbd6f669e103a3dd6f4632467aac8eb5650127c427`. Early harvest is now valued as two units over a three-day replant cycle, including seed and the existing action-cost convention; normal harvest retains the four-unit cycle. This corrects the identified optimistic branch, but uncertainty about crop displacement and servicing remains.

## Matched development results

Official environment 1.32.7; pinned COK and Seyam executables recorded in each manifest; seeds 0 and 2001, both seats. Each opponent contributes four matches. Mean paired cash-gap change compares exactly the same opponent, seed and seat with the frozen base in `data/raw/phase3-reserve-labor.json`.

| Opponent | Base wins | Corrected wins | Corrected mean cash gap | Paired gap change |
|---|---:|---:|---:|---:|
| COK | 2/4 | 2/4 | -967.75 | -626.50 |
| Seyam | 4/4 | 4/4 | +10,525.25 | -1,259.25 |

Equal-opponent mean gap change is -942.88. Two seeds provide too little independent evidence for a useful promotion interval. COK seed 2001 still loses by 15,956 in both seats. The initial inconsistent pilot also failed to improve paired mean gaps (COK -355.75, Seyam -1,126.50), so correcting the model did not reverse the rejection.

| Opponent | Measure, mean per game | Base | Corrected |
|---|---|---:|---:|
| COK | Harvested wheat | 174.75 | 198.00 |
| COK | Purchased wheat | 145.00 | 135.25 |
| COK | Purchased feed cost, excluding seeds | 6,000.75 | 5,574.50 |
| COK | Wheat cost, including seeds | 6,725.75 | 6,377.00 |
| COK | Strawberries sold | 278.25 | 255.00 |
| COK | Strawberry seeds purchased | 43.00 | 39.50 |
| Seyam | Harvested wheat | 168.00 | 208.75 |
| Seyam | Purchased wheat | 188.50 | 167.50 |
| Seyam | Purchased feed cost, excluding seeds | 8,165.25 | 7,113.00 |
| Seyam | Wheat cost, including seeds | 8,827.75 | 7,940.50 |
| Seyam | Strawberries sold | 221.75 | 205.25 |
| Seyam | Strawberry seeds purchased | 43.00 | 41.00 |

Harvested wheat is reconciled from sales + successful feeding - purchases, conditional on zero terminal carried/shed inventory and zero overflow. All measured games satisfy that condition. Purchased feed cost subtracts ten cash per wheat seed from the combined wheat expense ledger. Strawberry sales are realized sale quantities, not a hypothetical yield estimate.

All sixteen pilot/recheck games completed normally, with zero failed worker actions and zero candidate stderr turns. The corrected maximum measured policy time was 97.6 ms; the pilot maximum was 152.2 ms. These local timings are not hosted guarantees.

## Interpretation and reproduction

The intervention answers the causal policy question: growing more feed under this admission rule does reduce purchases, but fails to improve competitive returns. Additional feed purchases were not sufficient evidence that wheat was underallocated. The modest quantity savings coincide with fewer strawberry plantings and lower berry sales. Policy-dependent farm occupancy also changes random shop paths, so revenue differences cannot be attributed solely to those displaced units or treated as a fixed-demand experiment. A useful successor would price the full cohort that a wheat slot delays, including the option to buy feed when that preserves higher-value production; another fixed wheat target is not justified.

```powershell
.venv/Scripts/python.exe scripts/phase3_feed.py --valuation controller --output data/raw/phase3-feed-corrected-reproduction.json
.venv/Scripts/python.exe scripts/phase3_feed.py --valuation maturity --output data/raw/phase3-feed-pilot-reproduction.json
.venv/Scripts/python.exe scripts/phase3_feed.py --probe
```

The probe requires the four existing files under `data/raw/phase3-opening-diagnostic-replays`; it runs no games. Both candidate source snapshots are preserved under `reports/sources/<sha256>.py.gz`. Neither candidate changed the deployed policy.
