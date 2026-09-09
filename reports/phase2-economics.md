# Phase 2: economic model review

Reviewed 2026-09-09 against the installed official `kaggle-environments==1.32.7` interpreter. Incumbent executable: `750f123073865347efd3b9c4b72022ff9923f4130c929ac76c1b0742374b09ee`. This is a diagnostic study on previously used development seeds, not fresh validation.

## Ranked hypotheses

| Priority | Bottleneck and evidence | Expected impact / uncertainty | Smallest useful experiment |
|---|---|---|---|
| 1 | Crop lifecycle valuation penalizes melon and strawberry incorrectly. Official ideal melon harvest is day 10 with six units and one fertilizer; v7 charges a 12-day life and three applications. Strawberry eight units need two applications, not three. | Potentially changes production family and working-capital allocation; exact gains depend on executable watering and price saturation. Medium implementation effort. | Correct cohort cash-flow events, including action opportunities and marginal fertilizer yield; screen otherwise unchanged policy against both anchors. |
| 2 | Forecast uses observed prices mixed with base prices and a demand/supply ratio, ignoring observable market inventory and nonlinear price response. | High potential under wool/milk glut; uncertain opponent future supply. Medium effort. | Predict market inventory at each cohort's sale dates using current asset ages, held yield and uncertain future shops; apply the official price curve, validate forecast errors and candidate rankings. |
| 3 | Constant task values treat care, harvesting and manure collection almost independently of product prices. | Plausible wasted labor during gluts, but direct repricing harmed this screen. Must model delivery cost, deadlines and opportunity cost together. | A narrow low-price care suppression rule or workload-conditioned priorities, with crop losses and output as mediators. |
| 4 | Care before first production can exceed the holding cap; naive bank limits are themselves incorrect because care is banked after production. | Only two ideal actions saved per cow; low likely impact. Low effort. | Production-aware bank limit; do not introduce a naive cap. |

## Interpreter-backed lifecycle probes

Run `uv run python scripts/phase2_economics.py`. Production and watering are executed by the official interpreter. These probes assume perfect servicing and immediate harvesting; they are economic bounds, not a claim that the scheduler achieves them. They use no future randomness or private opponent information.

| Fertilized crop | Last / only harvest day | Total product | Fertilizer applications |
|---|---:|---:|---:|
| Tomato | 11 | 8 | 2 |
| Strawberry | 16 | 8 | 2 |
| Melon | 10 | 6 | 1 |

For strawberry, applications on days 9 and 13 cover production eves 9, 11, 13 and 15. Melon reaches its yield cap before its first legal harvest day. Continuing to charge fertilizer beyond that cap inflates cost. The current scheduler can also WATER before FERTILIZE when survival urgency overrides fertilizer priority; one-shot crop growth occurs immediately during WATER, so that ordering can lose the day's bonus. Ongoing crop fertilizer is applied at the overnight transition instead.

The exact ideal animal experiment feeds daily and harvests immediately through the transition to day 29:

| Animal | Daily care: actions / output | Naive cap: actions / output | Production-aware cap: actions / output |
|---|---:|---:|---:|
| Goose | 29 / 54 | 28 / 53 | 29 / 54 |
| Cow | 29 / 36 | 26 / 35 | 27 / 36 |
| Sheep | 29 / 34 | 28 / 33 | 29 / 34 |

`pending_care_bonus < max_held - 1` skips care on a production eve with a full old bank. That old bank is consumed first; today's care belongs to the next event. A correct cap must allow care on production eves. This rules out the naive cap even before considering benchmark performance.

## Counterfactual policy screens

Sixteen complete official games: two candidates, two pinned anchor opponents, seeds 42 and 103, both seats. The incumbent comparison comes from the saved final v7 audit on those identical scenarios. Opponents run and react normally to changed production; opponent cash is not held fixed.

| Policy | lonespear wins / 4 | Mean cash gap | GzmCR wins / 4 | Mean cash gap |
|---|---:|---:|---:|---:|
| Incumbent | 4 | +18,976.50 | 1 | −5,718.25 |
| Naive care bank cap | 3 | +11,811.00 | 1 | −6,788.75 |
| Bank cap plus price-scaled care / manure | 2 | +574.00 | 2 | −286.50 |

The combined repricing sets CARE to `clip(0.5 * current_product_price, 4, 160)` and manure collection to `clip(0.7 * fertilizer_price, 3, 90)`. Both candidates score 4/8 versus incumbent 5/8. Reject both as promotions. The second candidate's mean own cash against lonespear rises from 83,586 to 90,595 while its mean cash gap falls by 18,403: an explicit example of why absolute farm income is insufficient. Conversely its own cash against GzmCR falls by 12,740 while match score improves by one game. Two seeds do not establish a generalized gain or its cause.

Candidate hashes:

- Naive cap: `1e394168c97c9950ba154ba990c274723d75090e03b514d6e8460df5e88a65cc`.
- Combined economic priorities: `525e57bb2ea95f0b882d795a32d31730e1f4351c4bcce9417ff02609e62e6a8a`.

Full screening records are locally in `data/interim/phase2-economics/{capped,economic}-results.json`; each includes candidate snapshot, opponent hashes, interpreter provenance and episode telemetry. Exact candidate source snapshots are retained under `reports/sources/`. The historical incumbent's artifact is unchanged.

## Forecast and cash-flow limitations

The observed town-demand count is correct for the default configuration: shops consume six times per day, with single-product shops doubled, and the center consumes one unit daily. Forecasting unobserved shop identities as a uniform expectation is legal. It is not a calibrated price forecast: supply is an age-independent average across existing assets and the ratio adjustment neither integrates inventory nor predicts supply from future own investments.

Animal investment subtracts feed through day 29 and a constant action charge, but first production can include a larger accumulated care bonus than steady-state production. Conversely the assumed mature output requires executable daily care and enough harvest capacity. Crop plans charge a fixed action price rather than the observed marginal worker/travel cost. These are approximation errors, not evidence of hidden-state leakage.

The priority is therefore an age-aware, inventory-based sale-date valuation coupled to feasible work, followed by targeted confirmation in the official environment. Increasing crop biases or animal caps before correcting these economics risks optimizing around model errors.

## Adaptive herd follow-up

A second bounded experiment allocated 24 games to a materially different investment choice: remove the fixed species quotas and allow the existing observable-demand / supply forecast and finite-season net-return ranking to choose all animals, constrained only by a total herd limit of 12 or 18. All other incumbent behavior is unchanged. Seeds 17 and 103, both seats, two newly reviewed challenge implementations plus the lonespear anchor. The incumbent comparison reuses identical saved scenarios.

| Policy | Seyam wins / 4; mean gap | COK wins / 4; mean gap | lonespear wins / 4; mean gap |
|---|---:|---:|---:|
| Incumbent fixed 4 cows / 6 sheep / 8 geese | 1; −19,602.50 | 0; −33,350.25 | 4; +13,891.50 |
| Adaptive total 18 | 2; −1,971.00 | 0; −40,650.50 | 4; +16,961.00 |
| Adaptive total 12 | 0; −22,033.25 | 0; −52,945.50 | 4; +7,534.50 |

Adaptive 18 selects 13 cows / 1 sheep / 4 geese against Seyam on seed 103, but 9 cows / 4 sheep / 5 geese against COK on the same seed. The change therefore does respond to observed opponent supply. Its COK deterioration and tiny sample prevent promotion. Adaptive 12 loses all eight challenge games and is rejected. The apparent benefit against Seyam is worth revisiting only after more reliable sale-price forecasting; a fixed species cap is not necessarily optimal, but removing it alone is not a sufficient solution.

Candidates:

- Adaptive 18: `b52f2f2cdb7c4824f9257983e8259b806092d7249e5b69f9c2208c7ce26ac848`.
- Adaptive 12: `9c249546a0749bcf4cbb6ae862d0af2c0edadd939f39ff2f145e99267ebf9105`.

Complete manifests are locally in `data/interim/phase2-economics/adaptive18-results.json`, `adaptive18-anchor-results.json` and `adaptive12-results.json`; source snapshots are retained under `reports/sources/`. All 24 games completed normally. These are development diagnostics with no confidence or holdout promotion claim.

## Sale-date market model

`scripts/phase2_market_model.py` implements an isolated executable candidate, not a replacement simulator. It projects public market inventory from the current assets' crop ages and animal production dates, forecast feed consumption, uncertain care/manure output, and expected future shop unlocks. It then applies the official nonlinear inventory-to-price curve and averages a sale-date window appropriate to each new asset. A 50% blend with the observed quote limits reliance on the scenario. The forecast uses no future observations or opponent-private state.

The scenario assumes incomplete care (80% of an ideal steady-state bonus), 1.5 units per ongoing crop event, and manure collection from half the animals daily. It omits future replacement plantings and additional opponent investment. These are substantive modeling limitations; correctness of the price formula does not validate long-run supply forecasts.

Run `uv run python scripts/phase2_market_model.py --verify`. The default parameter dictionary exactly matches the installed interpreter; 5,148 product/inventory price comparisons and 18 empty-farm daily-price comparisons through actual environment steps agree. The first implementation mistakenly treated missing `market.params` as a reason to disable forecasting. Default observations omit that optional field. Eight completed games reproduced v7 exactly and were rejected as an integration failure, preserved in `market-default-guard-rejected.json`. The corrected implementation explicitly supplies the verified default parameters and respects observed overrides.

Run `uv run python scripts/phase2_market_model.py --diagnose-replays` for offline five-day forecast calibration on four already-inspected seed-0 challenge replays at days 0, 5, 10, 15 and 20. Future observations are labels only. Each product has 20 correlated checkpoints; no inferential confidence claim is made.

| Product | Keep-current-price MAE | Inventory-model MAE | 50% blend MAE |
|---|---:|---:|---:|
| Wheat | 5.00 | 1.45 | 2.78 |
| Carrot | 5.05 | 1.00 | 2.73 |
| Tomato | 3.20 | 1.15 | 1.88 |
| Strawberry | 24.05 | 6.25 | 11.65 |
| Melon | 57.15 | 4.90 | 26.13 |
| Egg | 1.85 | 1.20 | 1.38 |
| Milk | 27.00 | 13.15 | 17.93 |
| Wool | 52.30 | 20.55 | 35.43 |
| Fertilizer | 15.55 | 5.20 | 10.38 |

The model improves this short-horizon prediction diagnostic across every product. That result does not establish accurate investment-lifetime values or stronger play: changing production changes subsequent market supply. Complete calibration records are in `data/interim/phase2-economics/market-calibration.json`.

The companion input-reserve ablation raises the fertilizer sale reserve to 12–20 units. Inspection exposes a separate accounting error: `min(12, max(0, tasks - stock))` caps order size, whereas `max(0, min(12, tasks) - stock)` caps target inventory. When many tasks remain, the former repeatedly buys twelve even with enough reserve, then the selling policy liquidates the excess. Raising the sale reserve reduces this churn but does not correct the target-stock equation. That distinction must remain explicit when attributing ablation results.

The remaining 24 games in the 32-game budget tested three executable candidates on the same seeds 17 and 103, both seats. The intensive baseline is the previously screened `exact` policy: corrected crop lifecycle values, nightly transport, 60 crop slots, three quadrants and 12 hired hands, with fixed 8 cows / 4 sheep / no geese.

| Policy | Seyam wins / 4; mean gap | COK wins / 4; mean gap |
|---|---:|---:|
| Incumbent | 1; −19,602.50 | 0; −33,350.25 |
| Incumbent plus inventory model | 0; −18,908.25 | 0; −33,135.25 |
| Intensive exact baseline | 0; −35,585.50 | 0; −50,624.25 |
| Intensive exact plus larger reserve | 1; −22,766.00 | 0; −54,058.25 |
| Intensive exact plus reserve and model | 0; −72,050.00 | 0; −86,997.00 |

Reject all three as promotions. Better five-day price predictions did not repair poor investment and working-capital management. The model/reserve combination incurred 50 pre-terminal animal escapes across eight games, versus two for the reserve-only candidate. In the representative Seyam seed-17 seat-0 counterfactual, the model bought six cows and planted four melons on day 0, leaving 95 cash. Feed demand then cost more than available cash. The incumbent's purchase rule requires enough money for the **entire** feed shortage, so it bought none instead of an affordable subset. The hire reserve also prevented adding workers. Five cows escaped by day 3, before any melon could produce cash. This is a concrete failure mechanism and supports prioritizing opening liquidity and partial emergency feed purchase over forecast sophistication.

The larger reserve reduces mean fertilizer purchases against Seyam from 1,346.5 to 335.75 and against COK from 1,014.25 to 137.25, but still leaves substantial churn. All games completed normally with zero stderr turns. Maximum observed decisions were 255.4 ms for the incumbent-model candidate, 161.4 ms for reserve-only, and 106.6 ms for the combination under concurrent experiment load; these rejected candidates have not passed standalone deployment checks.

Exact executable hashes in `data/interim/phase2-economics/market-results.json`:

- Incumbent model: `b5fba54fb7075104c3f3dc824b7fe9a7ad78d08329b083973160d0b57d71895d`.
- Intensive reserve: `4ef1c2670bfeaec2d60a2d7c7150daccd6e3a0a4fb80e6eec8ecba090070ba89`.
- Intensive model and reserve: `0c67635244bf2092f82f70eb73ba1cf4a9aaf64238791798cab1e917088e8d4e`.

All source snapshots are retained. Subsequent lint-only formatting of the builder does not alter these frozen executed artifacts; reproduce their exact bytes with the snapshot restoration command.

## Funded market execution

`scripts/phase2_market_execution.py` tests sale timing independently of crop and animal production changes. For each shed product, it compares exact per-unit receipts from selling now with receipts after one or two days. Both alternatives include the price impact of the farm's own entire sale quantity. Delayed cash incurs a 1% daily charge and storage incurs one cash unit per product per day. The input products wheat and fertilizer retain the incumbent's existing reservation behavior.

The forecast uses current shops only and adds fully serviced production from publicly observed crops and animals, including current held output and our carried inventory. Holding is eligible only when that observable supply scenario remains smaller than known town consumption. It requires funded labor/feed obligations, keeps at most 24 units, reserves storage headroom, and stops before the terminal liquidation window. A third variant allows a funded position of at most five units when the same inventory model predicts positive resale profit after both buy and sell price impact. This is a bounded experiment with market risk, not risk-free arbitrage; future opponent investments and private inventories remain unknown.

The experiment separates three decisions: one-day holding, two-day holding, and two-day holding plus small funded purchases. It does not tune a grid of price thresholds. All policies retain the incumbent production planner. Synthetic guard probes establish that ample known milk demand permits holding, inadequate maintenance funds prohibit it, and day-29 observations force the original liquidation behavior.

A strategic limitation is that retaining our output also raises the prices available to competing producers. Improving our own sale proceeds may improve a larger opponent's proceeds even more. Match cash gaps, rather than isolated trading income, decide whether this component is useful.

The 24-game screen used seeds 17 and 103, both seats, with identical pinned challenge opponents:

| Policy | Seyam wins / 4; mean gap | COK wins / 4; mean gap |
|---|---:|---:|
| Incumbent immediate selling | 1; −19,602.50 | 0; −33,350.25 |
| Funded one-day holding | 1; −16,340.50 | 0; −44,768.00 |
| Funded two-day holding | 1; −21,073.25 | 0; −33,218.50 |
| Two-day holding plus eligible positions | 1; −21,073.25 | 0; −33,218.50 |

No candidate improves match score; reject all three for promotion. The one-day policy slightly improves the Seyam gap but materially worsens COK. The two-day policy remains near the incumbent, with mixed signs. No speculative purchase satisfies the economic and funding guards in these eight scenarios, so the third candidate reproduces two-day holding exactly. This is evidence that the proposed public-state opportunities were unavailable under these constraints, not a test showing active speculation is profitable.

Every game completed normally, with no stderr turns or storage overflow. Maximum observed decisions were 103.7 ms, 13.5 ms and 74.1 ms respectively under concurrent experiment load. The experimental source remains isolated from the deployed policy.

Exact candidates in `data/interim/phase2-economics/execution-results.json`:

- One day: `96e981b8f1188674d460f9ebd5673c31179f5329421c939cc83dfbe5aab671af`.
- Two days: `0f66c4f51da58fe3d38abd418c761f74e3fda17104b24c22822db5f915df8aea`.
- Position eligibility: `61ebb2ee421e08bd4a53ddc76e4dcd1acc80b5e5d65e8f3339ad3dd578b03c52`.

The largest observed gap still arises before market holding becomes affordable. These results support prioritizing early liquidity and production execution rather than adding this trading component to the incumbent.

## Adaptive herd after the liquidity/model interaction

The combined liquidity, market-model and expansion candidate subsequently became the strongest development challenger (`0098d9e4f77e2420cb4a09abd47e49f5160009cd0818ae37a793bc3e419ffc4b`). Adaptive species allocation was therefore retested on that stronger foundation rather than inferred from its earlier failure on v7. `scripts/phase2_adaptive_herd.py` allows at most 14 animals per species and either 18 or 22 in total. Owned animals awaiting placement count toward the total, and at most two may be pending, limiting forecasts that overlook unplaced purchases. No other production or scheduler behavior changes.

| Candidate / development panel | Seyam wins; mean gap | COK wins; mean gap |
|---|---:|---:|
| Fixed herd, seeds 17/103 | 4/4; +17,899.75 | 0/4; −35,825.00 |
| Adaptive 18, seeds 17/103 | 3/4; +6,652.50 | 0/4; −21,459.25 |
| Adaptive 22, seeds 17/103 | 3/4; +13,234.25 | 0/4; −23,875.75 |
| Adaptive 18, extension seeds 0/42 | 2/4; −2,832.75 | 0/4; −25,510.50 |

The 18-animal extension was justified by an observed mechanism, despite no initial COK wins: on seed 17 seat 0, it placed 12 cows, sold 318 milk and finished with 117,454 cash, compared with 63,486 for the fixed-herd challenger. COK also earned more, leaving a 20,648 deficit. On other scenarios, six to eight cows pushed day-20 milk prices to 3–36, limiting revenue despite higher output. Simply filling the milk demand with more cows can therefore erase the attractive current price.

Across all 24 additional games, neither adaptive herd wins a COK matchup. The larger herd does not improve the initial COK gap and adds obligations. These candidates remain unpromoted; the reduced COK deficit is a development observation, not evidence that its strategy-family gate is met. The next economic question is the value of retaining investment capacity until shop demand becomes observable, rather than committing most animal slots under the opening prior.

Exact candidates and locally retained complete records:

- Adaptive 18: `33cbb382042daf8732cc815fa764056ac20899958f8c937b47bd0e532aa70039`; `adaptive-model18-results.json` and `adaptive-model18-extension.json` under `data/interim/phase2-economics/`.
- Adaptive 22: `3ce96e20303ccbd0fbf8d42beaf4bb6698e8be04043c3634a5b3bad953615873`; `adaptive-model22-results.json` in the same directory.

All three manifests identify the identical frozen `0098d9e4...` base and retain exact candidate snapshots.

## Deferring herd flexibility until town evidence

One final eight-game screen tests whether waiting for two actual shop observations improves species allocation. In the default interpreter, shops unlock every three days, so the second observation arrives on day 6. `scripts/phase2_deferred_herd.py` uses the observed shop-instance count, never future identities. It preserves original 4/6/8 species limits until that point, then permits 14 per species, retaining the 18-animal total and two-pending-animal limits. The exact base is asserted to be `0098d9e4...`.

The fixed-herd reference has only 8–11 placed animals on day 6 in this panel, leaving investment capacity for the intervention. The policy does not explicitly reserve capital or animal slots, however; the species limits and pending-purchase guard also change early actions. It therefore tests this specific deferred-flexibility policy, not the general optimal value of waiting for information.

| Policy on seeds 17/103, both seats | Seyam wins / 4; mean gap | COK wins / 4; mean gap |
|---|---:|---:|
| Fixed-herd challenger | 4; +17,899.75 | 0; −35,825.00 |
| Immediate adaptive 18 | 3; +6,652.50 | 0; −21,459.25 |
| Two-shop deferred flexibility | 1; −7,311.75 | 0; −27,124.75 |

Reject the deferred candidate and do not extend the screen: it produces no COK win and materially weakens Seyam results. Its mean own cash against Seyam is 110,204.50, another example of increased absolute income without stronger match performance. By day 15 it has 11–13 sheep against Seyam, while COK seed 17 seat 0 leads it to 14 cows; observable demand changes the allocation, but that response is not sufficient for competitive improvement.

All eight games completed normally with zero stderr turns and a maximum observed decision of 105.9 ms. Exact executable: `21f8791fe0702046afbc83b6b4bffc98f9cb79274c23f6f772a943ba64b3c629`; full manifest and episodes: `data/interim/phase2-economics/deferred-herd-results.json`. The source is an original modification of this repository's frozen challenger and remains isolated from deployment.

## Marginal investment with existing-revenue effects

The final distinct economic probe asks whether valuing only the new animal's output overlooks damage to the farm's existing sales. `scripts/phase2_marginal_investment.py` builds on the same frozen `0098d9e4...` foundation with adaptive 18-animal limits. It projects two public-state scenarios: current assets plus already-owned pending animals, and those assets plus one prospective animal. Both use the existing observable inventory forecast. The new investment receives its projected output revenue, the change in existing own-herd revenue, additional feed cost, the feed-price change charged to existing own animals, capital cost and the existing service-time charge.

The scenario adds a one-day placement lag and uses the forecast's 80% care assumption consistently. It preserves actual crop and animal ages. Virtual assets exist only in copied observations used by the forecast; they are never game actions or privileged simulator state. A direct probe verifies that the original observation remains unchanged. Price and supply-model limitations from the earlier forecast study still apply: this is marginal value **within that scenario**, not an exact whole-farm cash-flow optimizer. In particular, crop-price revenue changes and opponent profit effects are not included in the objective.

The optional calculation checks a 40 ms budget between species and visibly falls back to the original cheap valuation. Its eight-game development screen was entirely separate from the already frozen candidate's validation and used only old seeds 17 and 103.

| Candidate | Seyam wins / 4; mean gap | COK wins / 4; mean gap |
|---|---:|---:|
| Fixed-herd challenger | 4; +17,899.75 | 0; −35,825.00 |
| Adaptive 18 | 3; +6,652.50 | 0; −21,459.25 |
| Marginal own-revenue valuation | 2; −6,296.00 | 0; −30,944.75 |

Reject without extension: no COK win, worse Seyam performance, and substantial runtime fallback activity. There were 148 turns with stderr across the eight completed games under concurrent load, with the marginal-budget fallback explicitly enabled; maximum observed decision time was 341.6 ms. These results evaluate that fallback-bearing executable and cannot isolate a hypothetical unlimited-runtime marginal policy. The expensive online calculation therefore lacks both performance and runtime evidence for deployment.

Exact executable: `76bd8db90f557c756ea15dfd8729e60fa8bc60ff4ceba389489a39057ab5a96d`; full frozen-source manifest and records: `data/interim/phase2-economics/marginal-herd-results.json`. The ongoing validation candidate and deployed incumbent were not modified by this experiment.

### Runtime fidelity follow-up

One additional eight-game run closes the runtime confound without tuning the strategy. Twelve evaluations of a single known day-15 COK observation took a median 4.53 ms and maximum 5.45 ms, returning all three species values. This supported increasing the optional forecast budget from 40 to 200 ms while retaining its in-execution fallback. The earlier artifact remains preserved. The budget literal is the only semantic source change; observations, objective, assumptions, seeds and opponents are unchanged.

| Marginal valuation executable | Seyam wins / 4; mean gap | COK wins / 4; mean gap | Stderr turns | Maximum decision |
|---|---:|---:|---:|---:|
| 40 ms budget | 2; −6,296.00 | 0; −30,944.75 | 148 | 341.6 ms |
| 200 ms budget | 2; −6,296.00 | 0; −21,984.00 | 0 | 105.0 ms |

All eight follow-up games completed normally. Removing observed fallback activity improves the COK cash gap, but produces no COK win and leaves the Seyam deficit unchanged. The intended marginal policy therefore remains rejected on performance evidence, rather than solely because of runtime fallback. Its COK gap is also slightly worse than the simpler adaptive-18 comparator (−21,459.25). No extension or new candidate selection follows this experiment; the frozen validation candidate remains untouched.

Follow-up executable: `cc94209c28f8f05b8013bcca6f54150619ee6e94289331d145ee57ef0227e652`. Complete provenance and records are in `data/interim/phase2-economics/marginal-herd-budget200-results.json`, with the single-observation timing probe in `marginal-runtime-probe.json`. Restore the exact follow-up bytes from the retained source snapshot for reproduction.
