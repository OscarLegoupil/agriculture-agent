# Collection urgency: independent review

The priority repair reduces deaths but does **not** justify promotion. Against
the same pinned Mooman opponent, seeds 5000–5007 in both seats, all three repaired
variants remain worse than the 150 ms cereal control. These are inspected
development scenarios, not fresh confirmation data.

| Policy | Wins / games | Mean cash gap | Water deaths | Overflow units |
|---|---:|---:|---:|---:|
| Common 150 ms control | 6 / 16 | −750 | 0 | 72 |
| Market collection | 6 / 16 | −11,640 | 210 | 0 |
| Market collection, priority repair | 6 / 16 | −5,499 | 87 | 0 |
| Land + seed collection | 0 / 16 | −21,409 | 78 | 41 |
| Land + seed collection, priority repair | 0 / 16 | −21,959 | 6 | 69 |
| Land collection | 0 / 16 | −20,277 | 26 | 128 |
| Land collection, priority repair | 2 / 16 | −16,985 | 6 | 54 |

There are no draws, candidate errors or stderr events in the repaired panels.
The matched control has one logged routing fallback. The repaired policies'
maximum measured decision times are 93, 88 and 126 ms respectively; median
per-game p99 decision times are 25, 17 and 15 ms. These measurements describe
this local panel, not hosted execution.

Compared with control, repaired market collection changes mean cash gap by
−4,748.5, with a descriptive paired-seed bootstrap 95% interval of
[−10,891.1, −561.3]. The corresponding land + seed and land-only changes are
−21,208.4 [−46,730.4, −790.1] and −16,235.1 [−41,174.7, +4,554.9]. Each seed's
two seats stay together in the resampling. Opponent-coverage uncertainty and
repeated development selection remain separate limitations.

The market repair recovers mandatory tomato service, but it still produces
487 fewer successful WATER actions and 406 fewer harvest actions than control,
while making 697 extra DROP actions across 16 games. Mean tomato receipts remain
5,182 lower; strawberry receipts improve by 2,048. Eliminating overflow through
frequent deliveries does not compensate for the service and production losses.
The capital repairs show that removing deaths alone is insufficient: their
production mix, sales and resulting public shop trajectories still differ, so
the remaining cash gap cannot be attributed entirely to scheduling.

## Two distinct failures behind the remaining deaths

All 87 repaired-market drought deaths are strawberries on days 20–25, with
future productive life remaining in representative losses. The implementation
can append HARVEST after required WATER on a mature ongoing crop even when held
yield is zero. Market-pressure valuation then clips the entire bundle's value
to held yield times price: zero. It discards the bundle before its required
priority can apply. The lost value includes future production, not just current
inventory.

For seed 5000 seat 0, replaying all 24 observed day-20 inputs through the frozen
repaired market source reproduces every recorded action. Strawberry (4,0),
planted day 7 and holding no product, is already dry at hour 0. Observable rival
supply triggers strawberry urgency through hour 9, but the target never enters
a route. When that pressure disappears, other route commitments and optional
fertilizer costs still prevent its recovery. The official plant transition
confirms its drought death at the day-21 boundary. The compact evidence lists
all 87 official-helper-verified deaths.

The capital repairs' six deaths occur on seed 5005, both seats, during day 10:
two young strawberries and one wheat at the far edge of the newly expanded farm.
This is a different opening-capacity conflict; the inherited melon race remains
protected. The priority repair does not prove that an earlier expanded farm can
be serviced during that race.

## The broader control also has an avoidable miss

The additional 48-game control panel contains two drought deaths: seed 5018,
both seats, at strawberry (8,1) on the day-24 to day-25 boundary. It was planted
on day 9, holds one berry, and has its fourth production event due at that
boundary. This is not terminal abandonment.

All 24 observed control decisions on day 24 reproduce exactly. The target is
reserved at hour 2 as FERTILIZE → WATER → HARVEST, then its entire route is
invalidated for unavailable inputs at hour 3. Another reservation at hour 4
is invalidated at hour 5. WATER remains unassigned afterward because its bundle
still carries optional fertilizer, pickup and harvest costs.

At hour 22, worker 12 stands on the already-watered neighboring berry at (8,0).
Its retained route contains only HARVEST. It harvests one berry and moves SOUTH
at hour 23, arriving at (8,1) as that plant dies. The minimum feasible service
route SOUTH → WATER was still available at hour 22.

A two-action official worker-transition counterfactual verifies the local
opportunity in both seats. SOUTH → WATER leaves the worker at the same location,
moves one berry from carried stock back to the neighboring plant without
overflow, and preserves two berries on (8,1) after refresh. Other workers retain
their recorded actions. This is an **offline local feasibility witness**, with
no market or reacting-opponent continuation; it is excluded from competitive
cash and score measurements.

## Candidate justified by the diagnosis

[`deadline_water.py`](../experiments/deadline_water.py) reserves mandatory
non-melon WATER independently of optional fertilizer and harvesting. Once the
observation acknowledges watering, ordinary task generation may request those
optional actions again. If retained optional work blocks a feasible required
water insertion, it can defer fertilizer, care, manure collection, delivery and
ongoing-crop harvesting. It preserves feeding, other watering, creation and
annual-harvest commitments, plus existing melon and startup hiring protection.

The control-only artifact is
`876c3197330df5e7ce0307ae0f283d9b9f951a9845dd0d14f2cfaa442df23583`;
the repaired-market composition is
`c638be9d49e923f328c380ffdc26fd9e98c67b5fc1e314e040678ce05c21ce3b`.
The focused tests establish the two-turn rescue in both seats, zero-held-yield
watering under rival pressure, missing optional fertilizer, preservation of
escape feeding, acknowledged follow-up fertilization, clean-process source
parity and state reset. Full-season evaluation is still required; this report
does not claim a gain for either new artifact.

Regenerate this review's compact measurements and diagnostic traces without
running a game:

```bash
python scripts/review_safe_collection.py
python -m pytest tests/test_deadline_water.py tests/test_market_collection_safe.py
```

The [evidence manifest](results/breakthrough-safe-collection-review.json) records
source identities, input-manifest hashes, official environment provenance,
per-seed paired changes, observed policy traces and replay hashes. Both local
diagnostics are clearly separated from competitive match outcomes.
