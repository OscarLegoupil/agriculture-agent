# Animal cohort receipts: startup value and placement assumptions

The incumbent understates ideal first-cycle yield, but its terminal event count
is **consistent with a one-day placement delay**. These are different findings:

- `1 + (28 - purchase_day - first_age) // interval` counts exactly the events
  through observation day 29 for an animal placed on `purchase_day + 1`.
  Do not add an extra terminal event without also changing that placement
  assumption. Same-day production and delivery on day 29 are possible; day-30
  output and terminal animals have no sale value.
- The incumbent credits `interval + 1` units on every event. With uninterrupted
  useful care and enough harvest capacity, first-cycle output is **six milk,
  six wool or four eggs**, followed by three, four or two units respectively.
  Its first-cycle understatement is three milk, two wool or two eggs per animal.
- A four-action official contract shows BUY_ANIMAL does not enable PICKUP in
  the same action phase; it does enable next-action pickup and subsequent
  same-day build/placement. Next-day placement is a conservative planning
  scenario, not a rule. Crowded routes or late purchases may take longer.

`scripts/phase4_animal_value.py` computes explicit production/sale dates, daily
feeding obligations and useful care days for a specified placement date. The
model applies production before adding that day's care, stops crediting bonuses
after the final saleable event and limits first output to actual holding caps.
Thirteen tests compare twelve species/placement cases with official animal
refreshes and exercise purchase/pickup/build/place through four official turns.
No full games are run.

## Example at purchase day eight, placement day nine

| Animal | Production days | First / later units | Total units | Feeding actions | Useful care actions |
| --- | --- | --- | ---: | ---: | ---: |
| Cow | 17, 19, 21, 23, 25, 27, 29 | 6 / 3 | 24 | 20 | 17 |
| Sheep | 15, 18, 21, 24, 27 | 6 / 4 | 22 | 18 | 17 |
| Goose | 13 through 29 daily | 4 / 2 | 36 | 20 | 19 |

Feeding after the last primary event is excluded only in this primary-product
plan, assuming held output is collected on its production day. Actual feed may
preserve unharvested output or produce valuable manure; omitted manure is not
automatically worthless. The plan cannot replace the controller's escape checks.

The optional `value_plan` sensitivity helper takes product/feed prices in
cash per unit and a declared worker opportunity cost in cash per action. It
charges animal purchase, feed, useful care, three-unit feed pickups, initial
build/pickup/place and each receipt's harvest/DROP. Travel actions must be
supplied separately. This is an explicit accounting interface, not a fitted
worker value or a route optimizer. Feed price uncertainty, market impact,
manure, shared deliveries and the alternative uses of existing workers remain
outside that simplified calculation. The inherited `(29 - day) * 12` charge
does not expose those separate assumptions.

## Smallest isolated valuation candidate

`build()` produces candidate
`84b1368926e09b9cefb7c8e2590a726400a49ba360fe89ceaefa581bf01e981c`.
It changes **only primary-receipt quantities** to the explicit cohort plan,
using next-day placement and same-production-day sale. It preserves v8's
forecast quote, existing feed and 12-cash-per-day charges, net/cost ranking,
cash guard, day-eight admission restriction and shared 18-animal cap. This
isolates the first-cycle correction before changing cost assumptions or
investment timing. It introduces no predicted future shops or private state.

On 36 known start-of-day observations from the four saved COK losses, the
candidate changes two actual BUY_ANIMAL decisions: both seats of seed 3029,
day eleven, switch **sheep to cow**. This is a concrete mechanism, not evidence
of an improvement; the extra first-cycle credit benefits cows most and may
aggravate a competitive weakness. The original scheduler already missed some
initial care, so ideal cohort receipts can overvalue an unserviceable admission.

Source bytes are archived under `reports/sources/<hash>.py.gz`; exact observed
purchase comparisons are in `reports/results/phase4-animal-value-probe.json`.
No screen is authorized or run by this audit. The next decision should weigh
this limited switch mechanism against the better-grounded initial animal
purchase/placement sequencing question, rather than assuming a more detailed
formula deserves promotion.
