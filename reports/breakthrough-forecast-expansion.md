# Forecast expansion and observed care banks

Omitted future rival berries are a real long-horizon forecasting limitation, but they do not explain the early model's initial berry preference by themselves. A more direct error is the constant animal-output approximation: it ignores the care already accumulated before first production. Correcting that public state substantially improves milk-price calibration in the saved games. Neither finding is a demonstrated match-score improvement.

## Scope and accounting

The diagnostic reads the frozen 150 ms capacity agent `fca083cdb5ac82dc4ad39a4227ef60ca57c948f819b565804aa706994f8e61ba` against pinned Mooman, seeds 5000–5007, both seats, at days 3, 6 and 9. These are 48 dependent checkpoints from 16 development games, not 48 independent samples. The environment is `kaggle-environments==1.32.7`; interpreter SHA-256 is `bc8a54879ef02c7ea64b8b333d6a976f0ea65c4949149d01f463f23bccee653e`.

Official action and market helpers reproduce all 23,008 recorded cash transitions. For each checkpoint, the raw market-inventory error is reconciled exactly into the omitted checkpoint-day flow, subsequent own net market flows, rival net market flows and the difference between expected and actual shop consumption. One-cash sales correctly leave market stock unchanged. Player-flow residuals include held goods, collection timing, model error and investment; they are not automatically attributed to new assets.

The comparison treats each future trace as the closing price for its labeled day, and compares it with the next recorded dawn. The source also omits the remainder of the checkpoint day, which is retained as a separate phase component rather than assigned to opponents. Recorded future trades, birth dates and shops are used **only for offline diagnosis**. Public expansion scenarios and the care-bank correction use checkpoint observations alone.

## What eight-day forecasts miss

Mean absolute quote error over each checkpoint's next eight labeled closing days:

| Commodity | Day-3 checkpoint | Day-6 checkpoint | Day-9 checkpoint |
|---|---:|---:|---:|
| Wheat | 1.3 | 2.0 | 1.7 |
| Tomato | 1.5 | 1.6 | 1.5 |
| Strawberry | 5.4 | 5.6 | 5.7 |
| Melon | 23.9 | 25.9 | 28.2 |
| Milk | 22.3 | 28.6 | 37.2 |
| Wool | 11.0 | 23.7 | 22.7 |

The public crop chronology rules out an eight-day berry-expansion explanation: new berries require ten days to produce. Mooman's berry births are identical in all sixteen inspected games: four on day 5, eight on day 6, four on day 7, four on day 8 and thirteen on day 11. Thus it has zero, four and twenty visible berries at the three checkpoints, and thirty-three by day 12. All berry harvests inside each eight-day window come from already visible assets.

Missing annual renewal is substantial physically. At day 9, the rival's next-eight-day wheat arrivals are forecast at 10.6 units, while actual harvests total 125.0; 122.4 units come from post-checkpoint cohorts. Yet the rival's net wheat market flow is only +2.4 units after purchases, and wheat-price error remains small. Harvested grain, market supply and final cash must not be treated as equivalent quantities.

Melon errors also principally involve existing crops. At day 3, predicted own arrivals are 72 units within the window versus 80.25 harvested, all from existing melons. The counterpart is 72 versus 72 for Mooman. Replacing only our forecast net trades with their recorded values reduces melon-price MAE from 23.9 to 14.5; the rival-only intervention reduces it to 18.1. These diagnostic interventions include timing as well as quantity. Shop replacement does not help melon in these windows because none of the inspected demand changes consumes it.

## Expansion matters farther out, on both farms

The long-horizon error is much larger. At the day-9 checkpoint, mean forecast strawberry price at the close of day 24 is 179.4; the measured price is 26.2. Substituting only realized future shop draws gives 152.9. Substituting only our recorded net market flows gives 149.1; rival flows alone give 124.9. These are separate interventions on a nonlinear price function and their quote changes must not be added.

In raw inventory units, the corresponding cumulative residuals are +45.8 from our net trades, +57.3 from the rival and +24.0 from shops, plus the separately recorded checkpoint-day component. New assets account for 112.6 of our 247.9 remaining berry harvests and 100.8 of the rival's 247.5. The error therefore includes both farms' future cohorts, not just an omitted opposing farm.

Three public supply scenarios test whether rival berries alone change early admissions: retain existing assets; expand toward seventeen berries; or expand toward thirty-four. Hypothetical commissioning is bounded to four sites per day, honors existing crop lifespan or first harvest, and assumes access to the first three quadrants through additional purchases spaced three days apart. New berries are fully fertilized. Cash, future worker capacity and actual opponent decisions are not solved; these are supply stresses, not executable opponent plans. No recorded future crop or shop enters them.

Applying the frozen finite-cohort ranker to the first currently empty site changes the preferred crop in only **4/48 checkpoints**: seed 5003 at day 3 switches from berry to carrot, and seed 5007 at day 9 switches from berry to wheat, in both seats. The common day-3 farmers'-market opening retains berry: its score falls from 1,079 to 1,002 under the thirty-four-berry scenario, above carrot 688 and wheat 663. By day 9, the effect can be large near a decision boundary: seed 5007's berry score falls from 616 to 290.5, versus wheat 606.

This rejects rival-berry expansion as a sufficient repair for the initial long-season preference. It does not establish that a complete farm calendar should ignore competing supply. The scenarios inspect first-cell rankings, not a joint financed batch or the opponent's response.

## A consequential care-bank correction

The source forecasts every future animal event as `min(capacity, 1 + 0.8 × interval)`. It discards the observable `pending_care_bonus`, including care accumulated during the long startup period. At day 3, our two visible cows are forecast to provide 10.4 units of milk in the next eight days; they actually provide 18, with no contribution from newly placed cows. The rival forecast is 13 versus 30 harvested, only six of which come from new cows. At day 9, rival milk is forecast at 58.5 versus 80.9 harvested, all from already visible cows.

The bounded correction carries the observed bank through each production event, consumes it before crediting that day's care, and retains the original 0.8 future-care intensity. It keeps the original feeding, collection, crop and future-shop assumptions. Completed care in the current observation is known rather than discounted to 0.8. A separate perfect-care diagnostic matches the official daily-refresh output for every observed animal at all 48 checkpoints.

| Milk forecast metric | Day 3 | Day 6 | Day 9 |
|---|---:|---:|---:|
| Original mean signed error | +17.12 | +25.53 | +36.44 |
| Observed-bank correction | −0.84 | −2.03 | +11.41 |
| Original mean absolute error | 22.31 | 28.59 | 37.16 |
| Observed-bank correction | 15.91 | 18.59 | 19.91 |

Residual error remains: future animals, demand uncertainty, feed procurement, service intensity and delivery are still assumptions. The perfect-care variant gives slightly lower milk MAE at days 3 and 9 but higher MAE at day 6; it is a contract check, not a selected production setting. Wool is less consistently improved because later shop draws dominate some of its errors.

`experiments/care_bank_forecast.py` isolates this quantity correction from the capacity parent and optionally composes it with the separately frozen price-floor forecast. Both preserve the deployed controller and the original 0.8 care assumption. Their SHA-256 identities are:

| Candidate | SHA-256 |
|---|---|
| Care bank only | `845abf20a4384d007464aaad7189cd9fd20a55240467e9f73ced7a55f0c66041` |
| Care bank and floor forecast | `5c57cd6d0ef539f34aa5dc0f74d865c14801a20bf5d83e50f7232a7c39076c1e` |

Fourteen tests cover official growth from observed ages and banks, held-goods separation, the terminal boundary, production-before-care ordering, exact preservation of forecasts without animals, official entrypoints and clean-directory execution. A matched game screen is still required; better calibration alone does not establish a stronger investment policy.

Each artifact also processes 2,157 recorded observations: capacity/Mooman seed 5007 in both seats, followed by seat 0 again to test reset. Independent source and official-loader namespaces agree on every action, with no stderr or budget fallback. Care-only p95/maximum time is 12.22/24.52 ms; the floor composition is 13.24/32.75 ms. These are off-policy runtime and parity checks, not matched-game outcomes. [Runtime measurements](results/care-bank-runtime.json) retain both source and replay hashes.

## Reproduce

```powershell
python scripts/forecast_expansion_diagnostic.py
python -m pytest tests/test_care_bank_forecast.py -q
```

The [compressed measurements](results/forecast-expansion-diagnostic.json.gz) retain replay hashes, configuration, public cohort timelines, all forecast and observed traces, supply-provenance counts, scenario commissioning calendars, rankings and exact inventory decompositions. No new game is generated by the diagnostic command.
