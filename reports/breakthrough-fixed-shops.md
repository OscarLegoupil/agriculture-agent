# Fixed-shop counterfactual: capacity, demand and runtime

**Extra productive capacity retains value when town demand is held fixed.** The
diagnostic also changes the interpretation of seed 5001: its poorer cereal
result is not adequately explained by removing nine berry positions. On the
reproducible seat, cereal improves the cash gap under the same town; the changed
town hurts more than production helps.

These sixteen games use an **altered environment and are ineligible for every
competitive score, promotion gate and rating claim**. Seeds 5000 and 5001 were
selected as known development witnesses. There is no fresh-data or statistical
strength claim here.

## Scope and control checks

Fleet `9400f9b0` and cereal `c2b3162d` each play reacting, pinned Mooman
`43326629` in both seats under both recorded donor town schedules. The installed
official interpreter is 1.32.7, SHA-256 `bc8a5487…653e`. The wrapper executes the
entire official daily transition, including weed and shop random draws, then
replaces only a newly appended shop. Agents see the current public shops at the
normal time; neither receives future shops. Prices, production, inventories and
opposing actions remain free to respond.

All sixteen games finish normally. **Seven of eight donor-policy controls
reproduce every recorded action and observation.** Cereal/5001/seat 0 fails
that requirement: the first difference is recorded step 489, following the
day-20 hour-8 observation. One hand moves south in the historical game and west
in the rerun. The original has one route-budget fallback; the rerun has none.
Its gap changes from −20,649 to −21,317. The evidence is consistent with a
runtime effect, but the old manifest does not locate its fallback precisely.
**Reject this control for exact historical decomposition.**

Three other cells contain four candidate route-budget fallbacks in total:
cereal under fleet's town on 5000/seat 0 (two), 5000/seat 1 (one), and
5001/seat 1 (one). Their contrasts are descriptive. No complete four-cell
factorial block is free of these limitations. Three-cell paths that avoid
those cells remain useful. Maximum recorded action time is 106.83 ms; the
largest per-game p99 is 46.05 ms. These timings do not remove the effect of the
policy's much shorter optional route deadline.

## Recorded cash gaps

Positive means candidate cash exceeds Mooman cash. These are diagnostic cash
outcomes, not additional benchmark wins.

| Seed / seat | Fleet, fleet town | Cereal, fleet town | Fleet, cereal town | Cereal, cereal town |
|---|---:|---:|---:|---:|
| 5000 / 0 | −26,243 | +4,363* | −8,292 | +68,413 |
| 5000 / 1 | −13,793 | +32,834* | +3,478 | +84,354 |
| 5001 / 0 | −15,950 | −11,009 | −26,522 | −21,317† |
| 5001 / 1 | −15,950 | −10,055* | −27,351 | −21,266 |

\* Recorded route fallback. † Historical control does not reproduce.

## A supported, explicitly ordered decomposition

Take this path: **fleet with fleet town → fleet with cereal town → cereal with
cereal town**. Both endpoint controls reproduce and none of these three cells
records a fallback on 5000/both seats or 5001/seat 1.

| Scenario | Town change, holding fleet fixed | Policy change, holding cereal town fixed | Total historical gap change |
|---|---:|---:|---:|
| 5000 / 0 | +17,951 | +76,705 | +94,656 |
| 5000 / 1 | +17,271 | +80,876 | +98,147 |
| 5000 / mean of seats | **+17,611** | **+78,790.5** | **+96,401.5** |
| 5001 / 1 only | −11,401 | +6,085 | −5,316 |

This is an exact accounting along the specified reproduced path, **not an
order-independent percentage caused by strategy versus luck**. Changing town
after changing policy can have a different effect. The reverse-order
seed-5000 contrasts suggest a large interaction, but include route fallbacks;
they cannot establish its exact magnitude. Seed 5001/seat 0 is excluded from
the accepted decomposition rather than averaged with its reproducible seat.

For seed 5000, the town-first stage raises fleet's mean cash by only 6,816;
it also reduces Mooman's mean cash by 10,795. The subsequent policy stage adds
79,927.5 to our mean cash and 1,137 to Mooman's. Holding opponent actions fixed
would therefore miss part of the effect on the cash gap.

## What changes in production and demand

**Seed 5000: more tomato volume survives the fixed-town comparison.** Under the
cereal town, fleet sells 56 tomatoes in each seat; cereal sells 186 and 158.
Tomato receipts rise by 75,093 and 78,004 respectively, explaining most of the
same-town policy gain. In seat 0, cereal has 34 berries and 23 wheat at the
start of day 15, then 24 tomatoes at the start of day 20; fleet has 43 berries
and seven wheat, then seven tomatoes. The extra positions can change crop.

The town change also matters. Running the official demand helper on the two
fixed schedules gives 162 and 108 additional tomato purchases, and 162 and
180 fewer berry purchases, over the season in seats 0 and 1. Fleet's tomato
receipts rise from 17,854/23,656 to 35,252/37,697 without increasing its
56-unit sales volume. Thus both market conditions and executable crop capacity
contribute; the original high-cash witness was neither pure demand luck nor a
pure production ablation.

**Seed 5001: demand reverses the apparent berry diagnosis.** On seat 1, changing
fleet's town reduces our cash by 4,674 and increases Mooman's by 6,727. Fleet's
berry receipts fall by 4,518 and egg receipts by 1,138. With that same town
held fixed, cereal sells fewer berries (268 versus 333) but earns 364 more
from them. Wheat receipts rise by 3,667 and wheat spending falls by 2,637,
including both grain and seed costs. Neither policy earns tomato revenue.
The cereal production change recovers 6,085 of the cash gap but cannot offset
the town's 11,401 loss along this path.

The [earlier observational review](breakthrough-capacity-review.md) correctly
identified missing berry quantity and changed shops together. This intervention
does **not** support attributing the seed-5001 regression solely to fewer berry
positions: own supply, prices and the opponent's response matter. Capacity and
commercial grain remain useful; robust adaptation to demand is still unresolved.

## Reproduce the interpretation

```powershell
python scripts/review_fixed_shops.py
```

The [derived evidence](results/breakthrough-fixed-shops.json) verifies all sixteen
archive hashes, both public observations' shop schedules, donor control
trajectories and candidate cash ledgers. It retains all cells, including failed
controls and fallbacks. Direct demand counts call the pinned official helper;
the review runs no policies, new games or random transitions. The separate
runner is [diagnose_fixed_shops.py](../scripts/diagnose_fixed_shops.py); its
default command only prepares cases.

The next causal question is whether the interaction survives consistent
optional-search budgets. Competitive confirmation must use the unmodified
environment, fresh matched scenarios and the frozen challenge pool.
