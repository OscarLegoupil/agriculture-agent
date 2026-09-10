# Scenario-based marginal herd valuation

The scenario model does not earn promotion. On the existing four-seed difficult
panel it preserves all Seyam wins and improves that cash gap, but produces no
additional COK wins and slightly worsens the mean COK deficit. This closes a
bounded model experiment; it does not establish that uncertainty modeling is
unhelpful in a better-calibrated planner.

## Hypothesis and implementation

The baseline averages future inventory before applying nonlinear prices, blends
that quote with today's price, and values a new animal independently of its
effect on existing own receipts. The candidate instead evaluates marginal
finite-season cash across eight deterministic, stratified future-shop paths.
Each future unlock uses a separate shuffled shop catalog. Paths can repeat shops
across unlocks, reflecting the official with-replacement process. A local fixed
generator constructs the design; it neither reads nor changes the environment's
random state. The eight paths are a dependent stratified design, not eight
independent samples supporting a statistical interval.

The model preserves current observable asset ages and accumulated care, includes
own unplaced animals, and adds one prospective animal placed the following day.
Primary production uses the first-event care cap and subsequent daily care
calendar. It includes daily fertilizer, feed, one-day harvest-to-sale delay and
zero credit for unsold terminal assets. One additional animal changes projected
market inventory and the prices received by the existing own herd and wheat
production. Valuation averages scenario cash, not the quote at average inventory.
The existing net-value/purchase-cost ranking, working-capital guard, opening,
18-slot herd limit and at-most-two pending purchases remain intact. Only animal
valuation from day 8 changes.

Worker opportunity cost is **4 cash/action**. Daily service charges include feed,
care, manure collection, half an action for amortized input/transport, and one
harvest per production interval, plus three startup actions. This is an explicit
approximation, not a validated route planner. The animal calendar assumes full
service; opponent future care and delivery also remain optimistic. Future land,
new opponent investment, crop replacement, and fertilizer consumed by future
crop servicing are not modeled. Wheat growth uses the existing observational
forecast scaffold. A three-point Simpson average approximates intraday price
impact; it is not exact order-by-order execution near price floors or branch
changes. These limitations can change animal rankings.

## Correctness, identity and budget

- Baseline `mixed_capacity`:
  `521467d45a0e2739d634ec628009753fe8e3844633bdc6e6f733f45521489a59`.
- Candidate `scenario_marginal`:
  `6750ea481374fb52393a1f941c9d3b4b7fc54d33d6ab46a0351d7dfb75602ba5`.
- Nine animal/calendar cases agree with the official daily-refresh helper,
  including existing and prospective cohorts and capped accumulated care.
- 1,035 price-curve cases agree with official `market_price`.
- Nine saved current-observation probes preserve their input unchanged and
  return all three values. The maximum model-only runtime was 8.51 ms in the
  recorded pre-screen check.
- The model checks a 120 ms deadline during evaluation. On expiry it emits a
  diagnostic and uses the existing cheap animal ranking. The full 16-game screen
  has zero stderr turns, no candidate failures, and maximum action time 52.95 ms.

These checks validate the reused price function and the stated ideal animal
calendar. They do not validate long-horizon forecast accuracy or ranking quality.
The experiment uses the unchanged pinned environment and opponents recorded in
[`results/phase3-scenarios.json.gz`](results/phase3-scenarios.json.gz).

## Matched development results

Seeds 2000, 2003, 2009 and 2013, both seats, were already known development
scenarios. These sixteen games consume no fresh validation or holdout. The
comparison retains all baseline scenarios and opponent versions.

| Opponent | Baseline wins / games | Scenario wins / games | Baseline mean gap | Scenario mean gap | Paired gap change |
|---|---:|---:|---:|---:|---:|
| Seyam | 8 / 8 | 8 / 8 | +13,765.88 | +22,244.88 | +8,479.00 |
| COK | 2 / 8 | 2 / 8 | -3,879.25 | -5,167.88 | -1,288.63 |

The COK changes are heterogeneous, not a uniform regression:

| Seed | Seat 0 gap change | Seat 1 gap change |
|---|---:|---:|
| 2000 | -4,292 | -12,885 |
| 2003 | +5,679 | +5,679 |
| 2009 | -7,187 | -7,279 |
| 2013 | +2,149 | +7,827 |

For 2009 the day-15 herd changes from fourteen sheep/four cows to eleven
sheep/five cows/two geese. Added egg receipts of 3,188 do not compensate for the
resulting whole-policy changes. In 2003, where milk and wool prices are weak,
the scenario model favors geese and improves both wins to a 13,807 margin. It
also improves the 2013 deficits, but still loses. These are measured full-policy
interventions; changed occupancy can change later shops and opponent actions.

The equal-opponent match score remains 62.5%, with COK at only 25%. Neither this
small repeatedly inspected panel nor a higher mean cash against Seyam is a
competitive promotion result. No extension or parameter search follows this
screen. Because calendars, co-products, uncertainty and marginal price impact
change together, this experiment cannot isolate which modeling component causes
the observed changes. Its strongest next use is forecast calibration against
realized service and supply, rather than increasing the number of scenarios.

```sh
uv run python scripts/phase3_scenarios.py --check-only
uv run python scripts/phase3_scenarios.py --workers 3
```

The builder asserts the exact baseline hash. Frozen candidate bytes are retained
under `reports/sources/`; the deployed policy is unchanged.
