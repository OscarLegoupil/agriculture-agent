# Why the larger opening still loses the field

The broad check rejects the six-seed impression of strength. The frozen
`febe9c76051a11e9ea7700e2d4701722e98274c51c50874ad03e1088b9398d4b`
opening wins 18/32 against Seyam and 2/32 against COK on development seeds
2000–2015, both seats. Its mean COK deficit is 20,940. The two largest diagnosed
losses come primarily from **capping sheep while buying lower-value cows**, not
from insufficient strawberry production or a large labor bill.

## Evidence and reconstruction

`data/raw/phase3-opening-field.json` contains the completed 128-game field check.
Saved 2002/2003 replays cover all four opponents and both seats, but those COK
games are near wins or small losses. Four diagnostic reruns therefore reproduce
COK seeds 2009 and 2013, both seats, using the unchanged executable and opponent.
All four final cash pairs and statuses match the original field exactly. They
are duplicate scenarios, not four additional independent observations.

`scripts/phase3_field_economics.py` reconstructs unit and market transitions on
copies of each recorded preceding observation. It calls the official helpers
and records successful trades, labor/land expenses, new cohorts and harvested
units for both players. It executes no policy and samples no random transition.
All **28,760 player cash transitions** in the twenty replays match the next
recorded balance. All twenty candidate ledgers also match the original benchmark
instrumentation. Private opponent inventory is used solely for this offline
accounting reconstruction, never as a deployable decision input.

The compact measured output is
[`results/phase3-field-ledgers.json.gz`](results/phase3-field-ledgers.json.gz).
It includes daily balances, compositions, cohorts, harvest quantities, actual
prices and shops, original replay hashes, and the official interpreter hash.
Environment: `kaggle-environments==1.32.7`, interpreter
`bc8a54879ef02c7ea64b8b333d6a976f0ea65c4949149d01f463f23bccee653e`.

```sh
uv run python scripts/phase3_field_economics.py
```

This command requires the saved replay directory; it does not launch games.
The duplicate severe-loss games are recorded in
`data/raw/phase3-severe-replays.json`.

## The severe deficit is mostly wool

The following accounting decomposition averages the four severe replay scenarios.
Positive differences favor COK. Product rows subtract all purchases of that
product, including seeds where applicable; gross wheat turnover is not profit.

| Cash component | COK minus opening |
|---|---:|
| Wool receipts | +40,810.25 |
| Fertilizer sales minus fertilizer purchases | +3,980.75 |
| Milk receipts | +77.25 |
| Strawberry receipts minus seeds | -1,618.00 |
| Melon receipts minus seeds | +1,938.00 |
| Wheat receipts minus purchased wheat and seeds | +5,534.50 |
| Carrot and tomato receipts minus seeds | -1,960.00 |
| Cow purchase expense saved | +1,600.00 |
| Additional sheep purchase expense | -4,000.00 |
| Additional land expense | -4,000.00 |
| Additional labor expense | -2,644.00 |
| **Final cash advantage** | **+39,718.75** |

On 2009 seat 0, COK sells 270 wool for 64,174 versus 85 for 19,868. The 44,306
wool advantage more than explains the 41,516 final gap before other components
offset it. Its milk receipts are only 2,134 higher, and its berry receipts are
6,736 lower. On 2013 seat 0, wool receipts differ by 38,740 out of a 40,181 final
gap; COK actually earns 806 less from milk. A strategy change justified as
"catch up in milk" would miss the principal opportunity in these cases.

The earlier 2002/2003 near-match replays show the same direction at smaller
scale: COK's extra wool receipts are 15,971 and 5,558 in seat 0. The candidate
offsets more of that difference with berry income. These are useful contrasting
cases, not substitutes for the severe losses.

## The consequential decision is already visible on day 8

Days below use the observation's zero-based `day`. In seed 2009 a Yarn Store is
observable by day 6. By the end of day 8 the opening has four sheep and four
cows; it then spends on cows until ten have been placed by the end of day 12.
COK instead grows its sheep cohort: six by the end of day 9, eight by the end of
day 11, ten by the end of day 13, and twelve by the end of day 17. It keeps six
cows. The same broad herd split appears on 2013, where the first Yarn Store is
already visible on day 3.

Re-evaluating the existing admission formula on the recorded current
observations, without exposing future state, gives:

| Observation day, seed 2009 | Sheep predicted net / purchase cost | Cow predicted net / purchase cost |
|---|---:|---:|
| 8 | 6.43 | 3.80 |
| 9 | 6.55 | 2.78 |
| 10 | 6.56 | 2.79 |
| 11 | 4.77 | 0.92 |
| 12 | 4.78 | -0.15 |

These are the policy's own forecasts, not realized profit estimates. They show
that the existing model already prefers sheep strongly. The fixed four-sheep
limit discards that option, so investment fills the cow allowance instead.
This is a capacity-allocation failure even before improving the forecast. The
initial cash-flow opening succeeds in funding a farm, but its later species
constraints direct that capital poorly.

At day 15 the opening is ahead in cash by an average 3,140 across these four
severe scenarios. COK is investing rather than merely possessing more opening
capital. Its average cash lead grows to 5,724.75 by day 21, 20,091.50 by day 24,
and 39,718.75 at termination. Final cash alone therefore dates the problem too
late: the investment decisions creating it occur roughly ten days earlier.

Across the full COK field, the ten games with a Yarn Store observable by day 6
have a mean deficit of 33,329, versus 15,309 for the other 22. This is a
post-hoc diagnostic split with correlated seats, not a new promotion test or a
causal effect estimate. It identifies a broader weakness consistent with the
replay accounting.

## Secondary opportunities and limits

1. **Include animal co-products in capital allocation.** Daily fertilizer is
   generated independently of the animal's product maturation schedule. The
   admission formula prices animal products, feed, purchase cost and a labor
   charge, but omits fertilizer income. COK's fertilizer advantage contributes
   roughly 4,000 net cash in the severe panel. Collection and sale feasibility
   matter: crediting every theoretically generated unit would overstate value.
2. **Value feed production and recycling on a net basis.** COK's gross wheat
   sales average 42,811, but wheat purchases and seeds cost 42,192.25. Its net
   wheat balance is only +618.75; the opening's is -4,915.75. That 5,534.50
   difference matters, but the gross sales cannot justify a huge wheat strategy.
   The accounts combine grown feed, commercial sales and purchased feed; exact
   action opportunity cost needs a separate executable cohort comparison.
3. **Treat fixed-price substitutions as bounds, not causal profit.** Replacing
   six cows with sheep would change own and opponent supply, prices, labor,
   placement, weed draws and future shop realizations. The observed wool
   advantage cannot simply be transferred into the candidate's score. Additional
   sheep must be evaluated with marginal total-farm receipts, funded feed and
   executable care/collection, rather than an uncapped copy of this ranking.

The highest-value next policy class is a funded mature-herd allocation that can
choose species according to observed demand and current supply while preserving
the productive opening. Its evaluation should distinguish admission limits,
co-product valuation and scheduler service quality. The previous unrestricted
adaptive-herd failures on `0098` remain negative evidence: this diagnosis does
not establish that removing every cap is sufficient, nor does it justify another
two-seed threshold search. Test against the established broader known field
before spending fresh validation data.
