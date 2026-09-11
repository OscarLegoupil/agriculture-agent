# Crop opportunity: prices, timing and the wheat multiplier

Enumerating uncertain shops is not the main missing capability in the inspected losses. Across 108 public-information crop, supply and delivery scenarios, optimizing expected receipts over the complete shop distribution changes the preferred crop in four cases. The largest modeled cost of selecting by mean-demand inventory instead is **32.19 cash**. The largest difference between the two valuations is **366.97**, but that difference rarely changes the decision.

A more concrete limitation is the admission rule's unconditional doubling of wheat value whenever fewer than 24 wheat tiles exist. The strongest inspected tomato opportunity is already selected on day 15. A later opportunity is blocked by that multiplier, even after the forecast sees profitable tomatoes. This motivated a bounded admission experiment, not a shop-scenario engine.

## Public-information diagnostic

The diagnostic uses C2b `c2b3162de26b82cb6057e94cb121b5655b7ee5c2e30659520f379f6ac7828b05`, Kaggle environment 1.32.7, Mooman development seeds 5001, 5002 and 5007, both seats, and day-15/day-18 observations. Five shops are visible on day 15 and six on day 18. With replacement and an eight-instance cap, the remaining paths can be enumerated exactly: 512 and 64 equally weighted paths respectively. No realized future shop, private rival inventory, environment seed or later opponent action enters a proposed decision.

Eight earliest wheat-renewal or empty sites are compared under wheat, carrot, tomato and fertilized-tomato calendars. New-cohort yields use official planting, watering, fertilizer, harvest and daily-refresh transitions. The source forecaster supplies current-asset production and feed demand; its imperfect-care assumption and daily discretization are deliberately retained to isolate the effect of a distribution. The mean enumerated inventory is checked against that forecast. Existing private goods are omitted in this diagnostic; the subsequent candidate accounts for observable own goods.

Three supply scenarios retain only finite current assets, renew other existing wheat sites, or additionally let eight rival wheat sites switch to fertilized tomatoes. These are assumptions derived from public assets, not a responding opponent or an adversarial search. Delivery takes zero or one day; terminal crops require same-day collection and sale by day 29. Empty day-18 sites test current-day and next-day commissioning. Worker cost is a four-cash shadow charge per action, with amortized travel and bulk delivery. The routes are not jointly scheduled, and next-day annual renewal is an optimistic execution assumption. Model percentiles below describe shop uncertainty under those assumptions; they are not confidence intervals for match outcomes.

For seed 5007, seat 0, next-day ordinary delivery, same-day terminal liquidation, and continued wheat renewal on other sites:

| Checkpoint and commissioning | Wheat net value | Fertilized tomato net value | Tomato advantage in cash gap | Shop-path p10 / p90 of advantage |
|---|---:|---:|---:|---:|
| Day 15, selected sites ready on days 16-17 | 2,033 | 7,216 | +4,991 | +2,722 / +9,152 |
| Day 18, empty sites planted that day | 1,788 | 4,249 | +2,334 | +1,584 / +3,363 |
| Day 18, planting delayed to day 19 | 1,916 | 3,481 | +1,478 | +683 / +2,508 |

The gap advantage also includes price effects on the opponent's prescribed production, so it differs from the two own-value columns' difference. New production is priced unit by unit with its own inventory impact, and existing owned production loses value when earlier new-cohort supply depresses its later prices. All tested new-crop sale prices remain above the one-cash floor, which the diagnostic asserts. The deployment prototype separately implements the official rule that floor-price sales pay one cash without adding market inventory.

The current observed deficits are 14,584 on day 15 and 25,565 on day 18 in this witness. **None of the enumerated paths allows the eight-site rotation advantage alone to erase the current deficit** in any inspected checkpoint. This is not a zero estimated win probability: future income from the rest of both farms, opponent adaptation and new investment are not solved by this calculation.

## What the actual selector does

The source is instrumented without changing its decisions at each day's first observable free crop-admission site. The values below are the parent's existing rate scores, not final-cash estimates.

| Seed, day/hour, free site | Wheat | Carrot | Tomato | Actual admission |
|---|---:|---:|---:|---|
| 5001, 15/12, (1,2) | 32.02 | 26.45 | 23.43 | Wheat seed purchase |
| 5002, 15/8, (1,7) | 31.43 | 23.29 | 28.67 | Melon seed purchase; melon scores 36.54 |
| 5007, 15/9, (8,3) | 33.49 | 23.29 | 63.45 | Tomato seed purchase |
| 5007, 18/0, (4,8) | 54.29 | 24.14 | 35.07 | Wheat selected with owned seeds |

C2b already chooses the large day-15 tomato opportunity and has ten tomato tiles by day 18. At the day-18 site, removing the wheat multiplier changes wheat's score to 27.14 and selects tomato. Removing only the current-price blend raises tomato to 44.07, but wheat remains ahead at 58.03. Removing both gives wheat 29.01 versus tomato 44.07. Matching the future-price window to the actual production events alone leaves tomato at 35.07 and wheat at 53.45, so it also does not change this decision.

The blend can understate late high prices, but the generic seven-day price window can overstate them too: on day 15 in seed 5007, restricting the tomato window to its four actual production events reduces its rate score from 63.45 to 52.25. It still wins. These effects should be distinguished rather than attributing every crop choice to an insufficiently aggressive forecast.

## Bounded implementation

`experiments/crop_opportunity.py` preserves the frozen 150 ms fleet and changes only crop admissions. It exposes three comparisons: remove the wheat multiplier from day 15, use finite remaining-season cohort receipts from day 15, and start that cohort selector on day 3. The earlier start also ends the forced opening crop rule at day 3; it is a materially different production experiment.

The cohort selector prices marginal funded batches against mean projected public inventory, charges seed and fertilizer costs plus worker actions and travel, preserves owned-seed sunk costs, includes observable own inventory, and charges price damage to existing owned production. It does not use the current-price blend or a fixed wheat multiplier. Immutable cached calendars retain crop ages, maturation, terminal delivery and a one-day annual turnaround. Shared seeds, actual commissioning and daily labor remain the existing route controller's responsibility.

Fifteen tests validate official crop transitions, planting and fertilizer schedules, terminal collections, the price-floor exception, preserved pre-admission behavior in both seats, seed sunk costs, immutable cache reuse, clean-directory loading and unchanged input observations. Both candidate source and clean artifact use the same implementation.

| Frozen candidate | SHA-256 | Cold-cache p95 / maximum |
|---|---|---:|
| No multiplier, day 15 | `7fb159182bdf32b97119b239730f208646070f99ee253a4388980d3da80dd263` | 11.20 / 33.40 ms |
| Cohort receipts, day 15 | `d59808d43fc55c9d348416d9d3d4f665a2c1d848ecc679a3d5ceacb4d4fccc1d` | 11.11 / 17.22 ms |
| Cohort receipts, day 3 | `9a83bb475173e00d1b5e2b28dada9c472e9e751139a5493ddbf1d3e5eb6a4652` | 13.46 / 23.69 ms |

Each candidate processed 2,157 complete recorded observations: seed 5007 in both seats, then seat 0 again to check episode reset. Cold and warm schedule-cache copies produced identical decisions, with no stderr or route-budget fallback. These are runtime and lifecycle checks on recorded states, not full-game performance measurements. Promotion requires the separately frozen matched game screen.

Remaining limitations are consequential: the executor may fail to renew a harvested site the following day; future rival crop renewal and investment are not in the deployed price path; private rival cargo is unknown; future fertilizer availability and bulk transport are forecasts. The absence of an explicit scenario engine is intentional because its observed decision value is small. The next diagnostic is whether requested admissions are commissioned on time and whether measured receipts support their projected advantage.

## Reproduce

```powershell
python scripts/shop_option_diagnostic.py
python -m pytest tests/test_crop_opportunity.py -q
```

The diagnostic reads the six retained development replays, preserving their hashes and effective configuration, and writes [compressed measurements](results/shop-option-diagnostic.json.gz). Replays remain outside version control. The saved output contains all 108 sensitivity cases and 12 actual selector witnesses; it contains no new game results.
