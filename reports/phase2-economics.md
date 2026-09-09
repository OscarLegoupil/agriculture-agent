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
