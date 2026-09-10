# What remains after feeding: workload diagnosis

The two severe recorded COK losses do not expose another large, free local-work correction. The agent takes longer routes overall and performs less productive work, but simple path detours and idle-on-useful-work cases explain only a small part of that difference. Several plausible logistics changes have already failed controlled screens; they should not be repeated under new names.

This diagnosis uses frozen v8 (`64fe3239…`), seeds 3029 and 3063, seat 0. It runs no games. All 1,438 regenerated actions match the saved actions exactly. The [compact results](results/phase4-workload.json.gz) contain observation-backed work alternatives, source/interpreter/replay hashes and official compressed-route witnesses.

## Realized work and its limits

| Metric | 3029 v8 / COK | 3063 v8 / COK |
|---|---:|---:|
| Available worker actions | 7,593 / 6,917 | 7,594 / 6,914 |
| Successful productive actions | 2,373 / 2,711 | 2,359 / 2,564 |
| Movement actions | 4,214 / 3,366 | 4,199 / 3,625 |
| PASS actions | 687 / 607 | 713 / 554 |
| DROP actions | 159 / 8 | 163 / 9 |
| Same-day wheat returned by DROP | 132 / 22 | 72 / 18 |
| Same-day fertilizer returned by DROP | 84 / 0 | 82 / 0 |

The successful-work counts come from the saved official-transition accounting in [phase4-execution](phase4-execution.md), excluding movement, pickup, delivery and no-op work. COK also uses selective PLACE deposits, so its low DROP count is not its total delivery count. Neither own loss has a water-deadline crop death or nonterminal animal escape; many apparent crop removals are scheduled lifespan expiry. More water-survival priority cannot explain these losses.

There is real input churn, but [selective delivery and broad delivery deferral](phase3-logistics.md) already failed their earlier screens. The current observation-based inventory delivery intervention also failed its broader phase-four panel. Reducing a logistics count does not automatically create executable high-value work.

## Matching and idle work: genuine imperfections, modest value

The matching pass includes workers which later choose DROP instead. This leaves a remote matched destination unserved on 64 turns in seed 3029 and 72 turns in seed 3063. The diagnosis confirms the mechanism against exact regenerated actions. However, excluding mandatory delivery workers from matching was already tested and rejected in [phase two](phase2-diagnosis.md). These observations do not constitute new evidence of a profitable full-policy change.

We test alternative local CARE, WATER, FEED and COLLECT_FERTILIZER actions for every actual nonterminal PASS using the official worker transition and shared resources at that worker's execution index. A change in a maintenance flag is only a legal action, not necessarily useful production. Later workers already performing the same local operation are excluded.

| Available local action at a PASS | 3029 observations | 3063 observations |
|---|---:|---:|
| CARE changes its flag | 52 | 11 |
| WATER changes crop state | 50 | 22 |
| COLLECT_FERTILIZER acquires one unit | 4 | 6 |
| FEED succeeds | 0 | 0 |

Of the 63 CARE opportunities, 49 occur on day 28, when many animals have no subsequent useful production. CARE can also be performed while unfed, but its bank does not accrue without feeding that day. Counting these actions as missed income would be incorrect. The water opportunities do not identify any recorded crop-survival loss, and legal WATER can change a flag without increasing a capped yield.

The fertilizer observations are repeated views of the same remaining units. Seed 3063's six opportunities are all the same goose at (4,9), day 17, hours 15–20: at most one additional daily manure unit, quoted at 50–52. Seed 3029's four observations concern three animal-day units quoted at 8–11 each. Even those quotes are upper bounds before collection timing, price impact and later sale feasibility. This does not support a substantial capacity improvement.

## Path compression supplies concrete but small witnesses

Keep each worker's original order of stationary work, then compare intervening movement with an in-board shortest path. Across the complete two games, excess movement is only **94 and 98 actions**, approximately 2.2–2.3% of own movement. This is much smaller than COK's 848/574 movement advantage. It excludes potential savings from changing the task order or farm layout, and cannot be interpreted as 192 freely reusable actions: market funding and action prerequisites can depend on when work happens.

Three selected delivery segments admit verified shorter routes on copied observed states:

| State | Original movement | Shortest movement | Officially deposited from observed inventory |
|---|---:|---:|---|
| 3029, day 14, hour 14, worker 7 | 9 | 3 | 1 fertilizer |
| 3063, day 10, hour 12, worker 2 | 6 | 2 | 4 wheat, 3 milk, 1 fertilizer |
| 3063, day 16, hour 15, worker 7 | 8 | 4 | 2 strawberries |

For example, at (3,3) in seed 3063, worker 2 can move SOUTH, EAST and DROP all eight carried units at (4,4). Official actions confirm available storage accepts the complete inventory. The observed continuation travels six steps before its DROP. The destination was selected retrospectively from the recorded continuation; the probe proves physical feasibility, not that an observation-only scheduler should always commit to that delivery immediately. It does not simulate the uses or cash effect of the saved time.

## Conclusion for the next experiment

The largest established local execution defect remains the shared-worker/feed admission issue already isolated in [joint maintenance diagnosis](phase4-joint-diagnostic.md). Beyond it, these losses support investigating coherent multi-task daily routes and executable asset workload, rather than another isolated priority threshold or repair for nonexistent water deaths. Such a planner would need to improve *which destinations are visited and in what order*: shortest-path movement to the currently selected destinations is already close to optimal. That is a larger hypothesis whose value has not been measured here.

No additional scheduler policy was implemented or promoted from this workload study. The evidence is intentionally a negative result for several cheap fixes, not a claim that the current scheduler is optimal.

```powershell
python scripts/phase4_workload.py
ruff check scripts/phase4_workload.py
```
