# Finite cohort economics: executable calendars and marginal sale prices

The base is the frozen phase-2 challenger `0098d9e4f77e2420cb4a09abd47e49f5160009cd0818ae37a793bc3e419ffc4b`. All experiments below use previously inspected development data: seeds 0 and 2000, both seats, against the pinned Seyam and COK references. Seed 2000's previous validation result is now known data; these are not new validation or holdout measurements.

## Hypothesis and model

The existing crop ranking combines average revenue per occupied day with approximate work and fertilizer costs. The proposed replacement enumerates a new cohort's legal watering, fertilizer, harvest and removal dates through the last sale opportunity. Existing assets retain their observed ages in the underlying market-inventory forecast. Prospective cohort output is then added to that forecast, with per-unit price impact on its own current and later harvests. Other newly considered same-day cohorts add supply too; currently existing plants are already present in the baseline forecast and are not counted twice.

`scripts/phase3_cohort_economics.py` makes the economic units explicit:

- Net cash receipts use the official inventory-to-price curve at forecast sale dates, including own additional quantities.
- Already owned seeds are treated as sunk expenditure; otherwise the seed purchase cost is charged.
- Fertilizer is charged at its current opportunity price, including home-produced stock.
- Tile actions plus an estimated travel and transport workload are charged at **4 cash per worker action**. The estimate includes one neighboring-tile move per service visit, shared four-unit fertilizer pickups, and shared five-unit inventory deliveries over the site's distance from the shed.
- The tested objective is net cohort profit divided by its occupied days through its final harvest. This is a renewal-rate heuristic with a finite season cutoff, not a full-farm terminal-cash optimizer. The builder also exposes an untested net-profit objective; no performance claim is made for that alternative.

Travel estimates assume batching and do not guarantee that the existing joint assignment realizes those routes. Forecasts assume the current assets' future servicing and expected future shops, without observing actual future shop identities, private opponent inventories, or future decisions. Subsequent replacement plantings are not modeled. Additional considered crops are a planning scenario, not proof that their seed purchases are funded.

## Interpreter contracts and execution alignment

Run:

```bash
uv run python scripts/phase3_cohort_economics.py --verify
```

Thirty calendars cover all five crops, planting days 0, 17 and 25, with and without fertilizer. Their harvested dates and quantities agree with official `WATER`, `FERTILIZE`, `HARVEST`, and daily plant transitions. The probes caught the consequential initialization detail that a fresh plant starts with one consecutive unwatered day and must be watered on its planting day. They also cover the four-event ongoing lifespan, product holding caps, and the source controller's harvest thresholds. Calendars stop watering on day 29 and require harvest by that day; the final delivery window is covered by the repository's existing interpreter contract tests, not these single-tile probes.

The first candidate uses feasible **fertilize-before-water** calendars for one-shot crops. This is an ideal servicing scenario, not an accurate description of the unchanged controller: prior telemetry shows it usually applies annual fertilizer after watering, which cannot increase that day's immediate growth. The second screen therefore disables one-shot fertilizer in both the physical controller and the economic calendar. Ongoing fertilizer remains enabled. This isolates a meaningful execution-alignment intervention, although the ongoing controller's price gate may still refuse an application assumed by the calendar.

No deployed source or previous artifact was changed. The candidate source is assembled in an isolated directory and snapshotted before each benchmark.

## Paired development results

| Policy | Seyam wins / 4 | Mean cash gap | COK wins / 4 | Mean cash gap |
|---|---:|---:|---:|---:|
| Frozen `0098d9e4...` base | 1 | −10,341.75 | 0 | −27,200.00 |
| Calendar rate, ideal annual fertilizer assumption | 0 | −28,585.00 | 0 | −22,298.00 |
| Calendar rate, recurring-only fertilizer | 0 | −23,261.50 | 0 | −16,746.00 |

Both candidates are rejected for promotion. Recurring-only execution alignment improves the COK gap relative to both the first model and the base, but does not produce a win and worsens the Seyam matchup. The smallest COK deficit is 9,988 on seed 2000, seat 0. No confidence or generalized-competitiveness claim is justified by this two-seed diagnostic.

The crop-selection mechanism does change materially: the first model has 30–33 strawberries against Seyam by day 15 and sells a mean 218.5 strawberry units. Against COK it sells 172 units on average; the aligned candidate sells 165.5. Increased berry production does not itself establish stronger play. Mean own cash against COK falls from 87,601.75 in the first model to 71,496.50 with alignment while the cash gap improves, demonstrating why opponent response matters.

All sixteen games completed normally with zero stderr turns. Maximum observed decisions were 94.3 ms for the first candidate and 44.4 ms for the aligned candidate. These experimental files have not passed release packaging or fresh validation gates.

## Reproduction and remaining question

```bash
uv run python scripts/phase3_cohort_economics.py --objective rate
uv run python scripts/phase3_cohort_economics.py --objective rate --recurring-only
```

Exact executed artifacts:

- Initial rate model: `aa9320502a0f7ffb5731dd86fdb170bf56ee86a27b94d2fe46eb3ee057b62c64`.
- Recurring-only alignment: `0fd83d4408b21ff50cbc5fa57db4e5aec12e688128d921f1d071397846de77c6`.

Complete records are in `data/interim/phase3-economics/rate-results.json` and `rate_recurring-results.json`, with exact snapshots under `reports/sources/`. `calendar-contracts.json` preserves every official probe's operation and harvest schedule. Restore the snapshotted source for exact historical executable bytes if subsequent builder formatting changes.

The evidence supports coupling cohort choices to startup liquidity and actual workload before revisiting crop ranking alone. The model currently values a feasible isolated calendar, while the full scheduler must service all overlapping cohorts, input trips, animals and liquidation work. That capacity coupling remains the main limitation of this replacement.

## Daily marginal labor from service routes

`scripts/phase3_labor.py` tests a different hiring rule on the frozen `startup_fert_reserve` policy (`dbd2a8418b57573cb6084712bfbcd2d18245fac83fcf18bc1ab7c39345b5d955`). It inventories remaining watering deadlines, harvest and decay windows, feeding, care, manure collection, recurring fertilizer, pending animal placement, and funded sowing/weed work. A greedy route model starts existing workers at their observed positions and new workers at the least-occupied legal shed-access spawn tile. New workers lose the current action because market hires become usable next turn. Routes use Manhattan travel plus approximate batched pickup/delivery work and reserve 20% of the remaining day's action capacity for scheduling error.

Additional workers are valued by the newly serviceable task value and charged their actual Fibonacci marginal hiring cost. The model funds feed and a cash buffer before extra wages, retains the original six-hand opening allowance for purchases not yet visible, and never assumes hired hands can be dismissed before the daily reset. It changes hiring only; the existing physical controller still chooses the actual work.

The first eight-game screen exposed a cash-accounting mismatch: reserving full feed expenditure plus 150 cash blocked inexpensive labor during the wheat bridge. In one representative game, day 2 began with 177 cash; the model assigned no hiring budget, and by day 3 seven plants and two animals had been lost. The second screen changes only that extra cash reserve to 20. The first artifact remains preserved.

| Policy, seeds 0/2001 in both seats | Seyam wins / 4; mean gap | COK wins / 4; mean gap | Mean wages | Mean idle actions |
|---|---:|---:|---:|---:|
| Startup reserve baseline | 4; +15,913.25 | 2; +639.75 | 8,028.00 | 1,104.00 |
| Route labor, 150 cash buffer | 0; −24,141.50 | 0; −26,734.50 | 7,061.38 | 1,166.63 |
| Route labor, 20 cash buffer | 4; +11,918.75 | 0; −11,581.75 | 8,478.88 | 1,153.25 |

The cash correction reduces recorded water deaths from 56 to one across the eight games and animal escapes from 16 to three, but does not improve labor efficiency or competitive results. Reject both variants. The corrected route model spends more on wages than the simpler baseline while leaving more idle actions. Forecast sowing work and batched service assumptions do not align closely enough with the actual controller, and hourly recalculation cannot undo an unnecessary morning hire.

All sixteen games completed normally with no stderr turns. Maximum observed decision times were 101.1 ms and 84.9 ms. Complete manifests verify the eight distinct expected scenarios, normal statuses and unchanged executed hashes:

- Initial route labor: `6e4d24859b1e7720cd970a3395b3b0bf785f69c2d2cf9c3fccfce56560841613`; `data/interim/phase3-labor/results-0.8.json`.
- Corrected reserve: `4b009faceb28d401b6d76c6c2a0b172bb97cb45e982a750569d5caa53fc2fd2c`; `data/interim/phase3-labor/results-0.8-20.json`.

The labor and cohort drivers now initialize their manifests as incomplete and mark them complete only after checking scenario coverage and final source hashes. Existing records were verified and annotated without rerunning any games.

## Independent anchor regression check

Two stronger opening candidates were checked against the frozen lonespear and Gzm anchors on seeds 0 and 2001, both seats. These sixteen games use the exact frozen artifacts; this check changes no policy and does not consume fresh validation data. The comparator reuses `0098d9e4...` records from the matching development and now-inspected validation scenarios.

| Policy | lonespear wins / 4; mean gap | Gzm wins / 4; mean gap |
|---|---:|---:|
| `0098d9e4...` | 4; +12,874.00 | 3; +9,013.50 |
| Startup reserve, 10-hand cap | 4; +28,075.00 | 4; +41,286.75 |
| Larger dairy herd | 4; +26,322.00 | 4; +48,016.50 |

Both candidates preserve anchor performance on this small panel and improve mean cash gaps. This supports broader evaluation rather than an anchor-regression rejection; two seeds do not establish generalized gains. The larger dairy variant has a narrow 179-cash win against lonespear on seed 2001, seat 0, despite its favorable aggregate.

Every game completed normally, with zero stderr turns. Maximum observed decisions were 63.6 ms for the startup candidate and 103.3 ms for the dairy candidate. Complete output manifests and current executable hashes were verified after execution.

- Startup reserve 10: `febe9c76051a11e9ea7700e2d4701722e98274c51c50874ad03e1088b9398d4b`; `data/raw/phase3-anchor-startup10.json`.
- Larger dairy: `7c1860fc15a28179b278305376123784a73f2954797f7e05fd5f335510f364cf`; `data/raw/phase3-anchor-large-dairy.json`.
- Compact paired summary: `data/raw/phase3-anchor-summary.json`.
