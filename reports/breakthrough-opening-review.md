# Common-budget opening and cereal review

Reviewed 2026-09-11 against source revision `fcacde604148b4a9aa1b2a8f166cd48e801ca81a`.

The fertilizer-only variant provides a modest, mechanically plausible cash improvement against Mooman. It wins exactly the same six matches as the capacity control. The extra-land variant earns slightly more average cash but loses two previously won matches. Neither result establishes stronger competitive performance. Renewal, early berry conversion, and clearing all routes on worker arrival also fail this development screen.

## Comparable evidence

The review covers `data/raw/breakthrough-opening-mooman.json` (80 games) and `data/raw/breakthrough-cereal-service-mooman.json` (48 games). Both contain seeds 5000–5007, both seats, and the same pinned Mooman bundle. These eight seeds have already informed substantial development. There is one independent opponent here, not a diverse competitive field or a fresh validation panel.

All 128 rows uniquely cover their declared panels. Source snapshots and executable hashes, opponent sidecars, environment/dependency identities, effective configuration, and resolved seeds verify. Both panels use kaggle-environments 1.32.7, interpreter SHA-256 `bc8a54879ef02c7ea64b8b333d6a976f0ea65c4949149d01f463f23bccee653e`, the default 720-step configuration, and the same 150 ms daily-route budget. All games finish normally. In every row, starting cash plus recorded income minus expenses equals final cash exactly.

| Identity | SHA-256 |
| --- | --- |
| Capacity control, 150 ms | `fca083cdb5ac82dc4ad39a4227ef60ca57c948f819b565804aa706994f8e61ba` |
| Extra land | `2cb7fb6a1a2ecca9e4fc96407ed900aa7ba9b1e0fb01f923e1985254bdba52cc` |
| Fertilizer only | `e88a6ec7dc337de178a0eef0ea880ca4ed647e7a5b329d8def4fcf80b08ebbe5` |
| Renewal only | `cfc2ad68c9ed23f61abb0d07ba681310f267f64728e9f8d7ccea232a6d4fe5dc` |
| Fertilizer and renewal | `ea2142924618b01672df5e52617f55d8d15bd706133106ae96cc9819342255d7` |
| Mooman executable | `4332662941c5eb6cb79c8d0acdb75ddf0d9c2ad66a7cb002787d3b99ffe19ded` |

## Matched results

Cash gap is own final cash minus opponent final cash. Draws score one half; none occurred. The independent uncertainty calculation resamples eight seed blocks, retaining both seats and every paired policy within each sampled seed: 40,000 bootstrap draws, NumPy generator seed 271828, percentile 95% intervals. These are descriptive development intervals, without a correction for screening several candidates or repeatedly inspecting these seeds. They do not measure opponent-coverage uncertainty.

| Candidate | Wins / 16 | Mean gap | Median gap | 10th-percentile gap | Paired gap change [95% interval] | Paired score change [95% interval] |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Capacity control | 6 | −750 | −12,856 | −25,977 | — | — |
| Fertilizer only | 6 | +2,359 | −12,369 | −21,438 | +3,109 [+148, +6,145] | 0 pp [0, 0] |
| Extra land | 4 | −7,796 | −10,177 | −21,723 | −7,046 [−24,248, +4,416] | −12.5 pp [−37.5, 0] |
| Renewal only | 2 | −10,725 | −14,242 | −25,669 | −9,975 [−22,087, +289] | −25 pp [−62.5, 0] |
| Fertilizer and renewal | 2 | −10,324 | −13,104 | −25,088 | −9,574 [−24,000, +1,927] | −25 pp [−62.5, 0] |
| Worker-arrival replan | 0 | −18,325 | −20,835 | −29,642 | −17,575 [−40,344, −2,979] | −37.5 pp [−75, −12.5] |
| Four early berries | 2 | −12,465 | −11,313 | −24,238 | −11,714 [−40,546, +8,761] | −25 pp [−62.5, +25] |
| Early berries and arrival replan | 2 | −15,274 | −18,371 | −25,939 | −14,524 [−40,135, +2,917] | −25 pp [−62.5, 0] |

The zero score-change interval for fertilizer is a property of identical observed match outcomes. It does not establish that its true score effect is exactly zero. All ten control losses remain losses, including both seats of seeds 5001–5004 and 5007. The positive mean gap is driven by large wins rather than broadly positive matchups: its median gap remains negative.

Fertilizer improves mean own cash by $2,192.50 [+$124, +$4,465]; opponent cash falls by $916.88 [−$3,830, +$1,578]. Six of eight seed blocks have a positive gap change. Seeds 5000 and 5002 account for 76% of the net gap gain. The leave-one-seed-out mean remains positive in all eight cases, between $2,082 and $4,084. This is useful evidence for a follow-up, not a promotion result.

Extra land improves mean own cash by $1,808.50 [−$14,571, +$14,840], while opponent cash rises by $8,854.75 [+$4,061, +$13,398]. Its negative mean gap change is sensitive to seed 5000: omitting that already-known seed would change it to +$922. Such exclusion would be post hoc and is not a valid selection rule. Both seed-5006 wins become losses.

## First divergence and runtime

All 48 cereal trajectories exactly match their corresponding control observations and actions through the first 192 executed decisions. There is no fallback-induced divergence before day 8. Renewal and combined service first change actions on day 8, hour 0 or 1. The first change in the seed-5000 replay is financing six wheat seeds; worker actions still match. This experiment therefore combines advance working-capital allocation and local renewal. It does not isolate the value of eliminating one return trip after harvest.

Fertilizer-only actually first changes an action between day 19, hour 1, and day 23, hour 3, depending on the scenario. The economic gate waits until fertilizer is cheap enough. Its observed effect is late-season annual-crop service, not an improved opening. All recorded fallback indices occur after the corresponding first intervention. Later fallbacks can still change trajectories.

The extra-land source differs from the control only by setting the total quadrant target to four. All 16 games buy a third plot, raising land expenditure from $3,000 to $7,000. The first action difference is that extra `BUY_LAND`, on day 12, hour 21 through day 13, hour 23. This is a test of a late, unconditional fourth quadrant under the existing labor and crop planner. It does not establish that every strategy buying three plots is inferior.

The early-berry intervention first changes the market order at day 5, hour 0. The arrival interventions first change actions at day 1, hour 8, when another hire becomes observable. Their regressions cannot be attributed to an unchanged or accidentally uninvoked intervention.

| Candidate | Visible route-budget fallbacks / 11,504 decisions | Maximum call time |
| --- | ---: | ---: |
| Capacity control | 1 | 180 ms |
| Fertilizer only | 4 | 211 ms |
| Extra land | 1 | 154 ms |
| Renewal only | 1 | 262 ms |
| Fertilizer and renewal | 3 | 226 ms |

All 128 games together contain 16 visible route-budget fallbacks. All maxima remain below the declared local 500 ms gate and official one-second action limit. Common wall budgets improve comparability but do not make the experiments bitwise deterministic. Confidence intervals above retain all recorded games, including fallbacks; discarding particular unfavorable fallback games would bias the comparison.

## Production, receipts, and market paths

The full-panel ledgers support a real grain mechanism. Compared with control, fertilizer-only sells 34.56 more wheat units per game and buys 19.19 fewer feed units. Wheat receipts rise $1,330.38 and combined wheat seed/feed expense falls $826.13. It uses 29.38 more fertilizer actions per game, sells 27.69 fewer fertilizer units, and buys 4.44 more fertilizer units. The associated fertilizer receipt decrease and expense increase cost $269.19 per game. These wheat and fertilizer terms account for $1,887.31 of the $2,192.50 own-cash gain. The rest is the net of changed service, sales, and prices in other commodities.

That gain has a service cost: recorded overflow increases from 72 to 240 units across the panel, or from 4.5 to 15 units per game. Nonterminal animal escapes are nearly unchanged, 92 versus 93. There are no water deaths in either control or fertilizer-only panel. Grain throughput is therefore improved without demonstrating that storage and delivery are now adequate.

Six selected replays were independently reconstructed using the official unit and market functions in `scripts/phase3_field_economics.py`: control versus land for seed 5000, control versus fertilizer for seeds 5002 and 5003, seat 0. All 8,628 bilateral cash transitions match the recordings exactly. No policies or random game transitions were rerun.

| Replay witness | Control | Intervention | Consequence |
| --- | ---: | ---: | --- |
| Seed 5002, harvested wheat | 384 | 439 | Fertilizer produces 55 additional collected grain units |
| Seed 5002, wheat cohorts commissioned | 115 | 120 | Faster turnover includes five additional actual plantings |
| Seed 5003, harvested wheat | 372 | 422 | Another 50-unit grain gain; this seat records a later budget fallback |
| Seed 5000, harvested tomatoes | 186 | 244 | Extra land raises volume but does not preserve realized sale prices |
| Seed 5000, tomato receipts | $110,345 | $61,424 | More tomatoes coincide with $48,921 less tomato revenue |
| Seed 5000, harvested strawberries | 254 | 172 | The larger farm also misses 82 berry units under its changed season path |

These records also invalidate a simple interpretation of paired seeds as identical realized demand. Harvest and planting changes alter empty cells, which alters the number of weed random draws before later town unlocks. The official environment therefore follows different shop paths after the policy intervention. This is a valid policy comparison under the official game, but an individual cash difference cannot all be credited to the targeted mechanic or to deliberate market denial.

In fertilizer seed 5002, our cash rises only $1,565 while Mooman falls $8,734. At day 21 the control unlocks a yarn store and the fertilizer replay unlocks a bakery. Mooman sells the same 161 wool units in both reconstructed replays, but its wool receipts fall from $15,899 to $6,415. Most of this seed's $10,299 gap improvement is therefore not our direct grain profit. In fertilizer seed 5000, the day-24 unlock changes from yarn store to farmers market; five fewer tomatoes sell for $10,163 more. These demand-path effects must not be described as the agent anticipating future shops.

Extra land raises average sold tomato volume from 59.63 to 121.50 units, while mean tomato receipts fall from $21,329 to $20,297. It adds approximately 133 watering actions and 47 harvest actions per game and reduces idle actions by 213, so the added land is being used. Extra utilization and volume alone do not establish positive marginal competitive value. Its seed-5000 cash gap falls $60,192 in seat 0: own cash falls $42,030 and opponent cash rises $18,162 after different late shop unlocks and reduced berry service.

## Decision

Retain capacity as the control. Fertilizer-only merits a fixed, broader comparison against the same opponents on unused registered development scenarios, followed by fresh validation if it survives. Treat its current gain as a modest cash hypothesis with an unresolved overflow regression. Do not promote any of the opening or renewal variants from this panel.

For renewal, the smallest informative next ablation separates seed-buffer financing from the local harvest/replant contract; for land, timing, production admission, and realistic service capacity remain open questions. These are hypotheses for future interventions, not reasons to reinterpret the completed losses. Keep the reserved validation and final holdout separate from the repeatedly inspected 5000-series development data.

The canonical result report can be reproduced without games:

```powershell
.venv/Scripts/python.exe scripts/breakthrough_report.py --input data/raw/breakthrough-opening-mooman.json data/raw/breakthrough-cereal-service-mooman.json --champion fca083cdb5ac82dc4ad39a4227ef60ca57c948f819b565804aa706994f8e61ba --output data/interim/opening-common-budget-report.json
```

The canonical generator uses its own fixed bootstrap seed and draw count, so endpoints may differ slightly from the independent bootstrap above. No local result in this review establishes a Kaggle rating or a live leaderboard rank.
