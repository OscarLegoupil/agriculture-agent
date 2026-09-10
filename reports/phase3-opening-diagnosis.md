# Diagnosing the stronger opening against COK

The subject is `startup_fert_reserve10`, exact executable SHA-256
`febe9c76051a11e9ea7700e2d4701722e98274c51c50874ad03e1088b9398d4b`.
Four official games reproduce seeds 0 and 2001 in both seats, saving complete
replays. Their final cash matches the completed reserve/labor screen exactly.
These are repetitions of known development scenarios, not additional validation.
No policy changes are made in this diagnosis.

| Seed | Seat | Opening cash | COK cash | Cash gap |
|---|---:|---:|---:|---:|
| 0 | 0 | 97,537 | 84,523 | +13,014 |
| 0 | 1 | 118,083 | 93,646 | +24,437 |
| 2001 | 0 | 67,911 | 87,319 | −19,408 |
| 2001 | 1 | 67,911 | 87,319 | −19,408 |

## The opening cohort is now competitive

At day 1, hour 5, both farms have twelve melons, seven wheat, two cows and two
sheep. This removes the previous challenger's large initial crop deficit.
By day 7 the new opening has eleven strawberries against COK's six, and by
day 8 it has approximately twenty-three against eight. It is no longer
appropriate to diagnose these losses as simply planting the first berry cohort
too late.

The first consequential remaining investment difference appears on day 3.
COK places an additional cow then and another on day 5. The new opening holds
its herd at two cows and two sheep until day 8 even though cash at hour 5 is
712 on day 3 and 1,195 on day 5. Maintaining working capital has value, but the
hard gate prevents any marginal investment test during this interval.

In seed 2001, the actual cow placement cohorts are:

| Farm | Cow placements by day |
|---|---|
| Opening | Two on day 0; three on day 8; four on day 10; one on day 11 |
| COK | Two on day 0; one on day 3; one on day 5; two on day 7; two on day 9; two on day 11 |

At day 10, hour 5, the opening has already purchased its third quadrant and
has cash 501 with seven cows. COK still has two quadrants, cash 1,544 and eight
cows. By day 12 both have ten cows, but equal current herd size conceals the
different asset ages and remaining production opportunities.

## Investment timing versus servicing

Recorded actions were reapplied to copied observations through the official
unit transition function to count actual harvests. A separate ideal-servicing
probe uses each farm's actual animal placement days, with daily feeding/care
and immediate collection through the final production opportunity. This is
an offline upper bound, not an executable alternative or a cash forecast.

For seed 2001, seat 0:

| Product | Opening harvested | Opening ideal servicing | COK harvested | COK ideal servicing |
|---|---:|---:|---:|---:|
| Milk | 242 | 249 | 279 | 279 |
| Wool | 78 | 104 | 120 | 120 |

**Thirty of the thirty-seven missing milk units arise from the observed
placement schedule**, even under identical ideal servicing. Only seven milk
units remain between the opening's actual harvest and its own cohort ceiling.
The wool gap splits into sixteen units attributable to cohort timing and
twenty-six below the opening's servicing ceiling. A sheep escape contributes
to the latter category; not all pre-terminal losses are deliberate abandonment.

This identifies a stronger next experiment than indiscriminately adding hands:
permit staged additional cows before day 8 when current cash, next-day feed,
worker costs and existing crop obligations are covered. Keep the successful
initial wheat/melon cohort and the existing marginal animal valuation. The
quantity difference is not a claim that moving purchases earlier would recover
the full cash deficit: prices, task competition and opponent responses change.

The existing 11-/12-hand screens do not isolate labor value. On seed 2001 the
12-hand variant loses by 9,087 rather than 19,408, but earns only 55,224 versus
the 10-hand variant's 67,911; COK's cash and realized shops also change. Calling
the gap improvement a causal return on two extra workers would be incorrect.

## Why seed 0 wins while seed 2001 loses

The largest realized revenue difference is in berries:

| Seat-0 game | Strawberries sold | Strawberry income | Mean realized sale price |
|---|---:|---:|---:|
| Seed 0 | 295 | 62,945 | 213.37 |
| Seed 2001 | 260 | 29,842 | 114.78 |

Production falls by about 12%, while berry revenue falls by about 53%. The
realized price difference is substantially larger than the output difference.
Seed 0's final shops include three farmers markets, two ice-cream shops and a
brunch spot. Seed 2001 instead includes multiple pizza and smoothie shops and
a late yarn store. The same policy encounters a more valuable milk opportunity
in seed 2001, precisely where delayed cow cohorts leave production unavailable.

These are realized whole-game paths. Occupancy changes the daily RNG draws
before shop selection, so even same-seed staffing interventions need not face
the same future shops. The observed association supports demand-sensitive
investment timing; it does not license future-shop knowledge in the policy.

The opening also harvests only 213 wheat in seed 2001 versus COK's 386. It buys
163 wheat for 7,666 while selling 94 for 4,081. This does not prove that every
purchase/sale cycle is wasteful—early feed and later surplus differ—but it
motivates matching short-crop cohorts to known feeding obligations and using
input-specific reserves rather than a fixed seven-wheat target throughout.

## Ranked next hypotheses

1. **Replace the fixed day-8 herd gate with funded marginal investments.**
   Preserve the initial cohort, then admit a cow on days 3–7 only when its
   observable expected receipts cover feed, service and working-capital costs.
   The actual-cohort milk ceiling supplies direct evidence for this question.
2. **Plan wheat cohorts against the existing herd's near-term obligations.**
   Evaluate the tradeoff between purchased feed and additional timely wheat,
   including crop space and the avoided liquidation/replenishment flow.
3. **Target sheep service defects before raising the whole-season labor cap.**
   Twenty-six wool units separate realized and ideal servicing in the loss,
   while the analogous milk shortfall is only seven. Deadline-specific service
   or temporary labor is a more focused experiment than twelve hands every day.

Replay manifests are in `data/raw/phase3-opening-diagnostic-games.json`, with
replays under `data/raw/phase3-opening-diagnostic-replays/`. The four reruns
complete normally and reproduce their original cash exactly. Source is pinned
through the existing content-addressed snapshot; no release is promoted here.

## Counterfactual early-investment screen

The next sixteen complete games test the actual investment hypothesis on the
12-hand `startup_fert_reserve` base, SHA-256
`dbd2a8418b57573cb6084712bfbcd2d18245fac83fcf18bc1ab7c39345b5d955`.
All comparisons below use that exact 12-hand baseline, not the preceding
10-hand diagnostic subject. Both variants retain the existing marginal-return,
cash and feed admission checks.

- **Cohort funded:** once twelve melons exist and day 3 begins, release the
  normal herd caps instead of waiting until day 8.
- **Staged cows:** retain two sheep until day 8 and release one extra cow slot
  every two days beginning on day 4, provided twelve melons remain established.

| Intervention | COK wins / 4 | COK mean gap | Paired gap change | Seyam wins / 4 | Seyam mean gap | Paired gap change |
|---|---:|---:|---:|---:|---:|---:|
| Cohort funded | 0 | −17,068 | −17,707 | 2 | +11,669 | −4,244 |
| Staged cows | 1 | −3,021 | −3,661 | 2 | −877 | −16,790 |

Neither intervention is promoted. Earlier production is feasible: the first
extra cow appears on day 3 against COK under the first variant and day 4 under
the second. Contemporaneous cash before those placement actions is 409 and
549 respectively. These are placement-time balances, not the cash paid for
the earlier animal purchase.

The counterfactual exposes the omitted opportunity cost. Releasing investment
early produces more milk but delays follow-on strawberries: against COK the
unrestricted variant has only 11–12 strawberries at day 10, versus 22–23 in
the fixed-day-8 baseline. The staged alternative retains twenty, but still
does not improve results across both opponents. Preserving the first twelve
melons is insufficient to protect the opening's whole cash-flow sequence.

The refined hypothesis is to price displaced crop cohorts and their service
obligations in animal investment decisions. A positive isolated animal return
and enough cash for today's purchase/feed do not establish that the investment
is better than timely planting of the next crop cohort. The original placement-
schedule diagnosis remains valid; its proposed simple remedy fails the
official counterfactual test.

Run `uv run python scripts/phase3_investment.py --workers 2` to reproduce the
sixteen-game screen. `data/raw/phase3-investment.json` stores all results,
candidate snapshots, first-expansion-cow timing and cash, and full replay
locations. Opponents react normally; realized future shops may change with
farm occupancy. No causal claim assumes identical future demand paths.
