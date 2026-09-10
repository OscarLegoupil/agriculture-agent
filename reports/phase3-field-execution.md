# Field execution diagnosis and annual harvest intervention

The expanded development field rejected the narrow opening screen as sufficient evidence of strength. This diagnosis examines the frozen `febe9c76051a11e9ea7700e2d4701722e98274c51c50874ad03e1088b9398d4b` policy against COK in recorded seeds 2002 and 2003, both seats, without running additional diagnosis games. Seed 2002 seat 0 is a close win (+522 cash); seed 2003 seat 0 loses by 3,220. Physical measurements below use seat 0; the JSON retains both seats.

## What COK physically executes better

| Measurement | 2002 ours | 2002 COK | 2003 ours | 2003 COK |
|---|---:|---:|---:|---:|
| Available worker actions | 6,717 | 6,914 | 6,677 | 6,914 |
| Successful productive actions | 1,922 | 2,459 | 1,837 | 2,543 |
| Movement actions | 3,688 | 3,624 | 3,604 | 3,625 |
| PASS | 837 | 554 | 968 | 554 |
| Immediate reverse movements | 46 | 32 | 64 | 32 |
| DROP | 147 | 9 | 155 | 9 |
| Wheat returned by DROP | 107 | 18 | 134 | 18 |
| Fertilizer returned by DROP | 77 | 0 | 81 | 0 |
| Wheat harvested | 137 | 386 | 161 | 386 |
| Strawberries harvested | 297 | 271 | 278 | 274 |
| Milk harvested | 131 | 153 | 110 | 222 |
| Wool harvested | 106 | 180 | 107 | 162 |

Productive means a state-changing crop, animal, clearing, construction or animal-placement action. It excludes travel, waiting, input pickup and product delivery. Recorded unit actions are reapplied sequentially to copied observations with the official interpreter, including shared-seed contention. Immediate reversal counts two consecutive movement actions that return the same worker to its previous position within the same day; it does not claim every reversal was avoidable.

COK performs 28-38% more productive work with only 3-4% more available worker actions and essentially the same movement count. A few dozen reverse steps do not explain this gap. The incumbent's same-day DROP returns substantial inputs, but the previous selective-delivery ablation already showed that eliminating this churn alone did not establish better outcomes. More productive work is partly a consequence of owning more useful assets, not proof of an independently superior scheduler.

The fixed observed-herd service ceiling makes that distinction explicit. In seed 2003, ideal feeding/care and immediate collection on our actual placement cohorts produces 120 milk and 116 wool versus actual 110/107. COK's actual cohorts could produce 237/164 versus actual 222/162. Thus the 112-unit milk deficit is dominated by the 117-unit difference between cohort ceilings, not ten recoverable units on our existing cows. Our herd contains two initial cows plus two on day 8; COK adds cows on days 3, 5, 7 and 9, reaching eight. The previous earlier-investment experiment nevertheless lost by delaying valuable crop cohorts: buying earlier without financing the displaced production is not a demonstrated remedy.

Seed 2002 has a similar distinction: actual milk 131/153 versus cohort ceilings 156/189, wool 106/180 versus ceilings 116/208. These ceilings hold actual placement dates fixed and omit the extra worker time needed for perfect care; they are offline diagnostics, not deployable forecasts.

## A concrete action-order defect

The crop controller creates an expiry HARVEST task before an unwatered annual crop receives its last growth increment. At age four, wheat with three units has both HARVEST value 70 and WATER value 65, so the missing fourth unit is discarded. In these replays the incumbent never harvests four-unit wheat. It harvests three units at age four 26 times in seed 2002 and 30 times in seed 2003. COK does harvest four units 39 times per replay, although it also has incomplete harvests.

Applying official WATER then HARVEST to each recorded harvest state adds 33 wheat and 20 carrots in seed 2002, and 38 wheat and 40 carrots in seed 2003. Each extra unit requires one extra local action. These are immediate copied-state counterfactuals, not a feasible whole-season upper bound: some insertions would interfere with other deadlines or deliveries. COK itself leaves 48 wheat and one carrot under the same diagnostic. Its much larger wheat output primarily reflects more cohorts, not solely this action-order improvement.

The smallest informative intervention prioritizes WATER and suppresses that crop's HARVEST only when an observed worker can reach it, water, harvest, and, on day 29, deliver before the final action. Expiry rescue remains available if two local actions no longer fit. Annual WATER can earn an immediate terminal-day increment; recurring watering does not receive this exception. No fertilizer is introduced by this change.

## Controlled intervention screen

`scripts/phase3_harvest.py` builds artifact `0413a45398b4713d255f2c2fbfd587e045cccf9fcdb8d765495efced15f1d42e` from the frozen opening. Five focused checks run the actual candidate and the official unit interpreter: ordinary age-four wheat becomes WATER then HARVEST for four units; hour-23 expiry retains immediate HARVEST; terminal hour 20 at shed permits watering, harvesting and delivery, whereas hour 21 rejects the extra watering action.

The authorized sixteen-game screen uses COK/Seyam, seeds 2000, 2003, 2009 and 2013, both seats, matched against `data/raw/phase3-opening-field.json`. These are known difficult development cases, not fresh validation.

| Opponent | Base wins | Intervention wins | Base mean cash gap | Intervention mean gap | Paired gap change |
|---|---:|---:|---:|---:|---:|
| COK | 0/8 | 0/8 | -29,958.25 | -7,420.38 | +22,537.88 |
| Seyam | 6/8 | 4/8 | +11,753.25 | +8,071.25 | -3,682.00 |

| Mean per game | COK base | COK intervention | Seyam base | Seyam intervention |
|---|---:|---:|---:|---:|
| Own final cash | 79,155.00 | 56,628.13 | 88,014.13 | 79,418.75 |
| Harvested wheat | 174.38 | 213.88 | 175.25 | 198.38 |
| Wheat purchased | 170.88 | 147.38 | 127.25 | 151.88 |
| Wheat expense, including seeds | 7,639.50 | 6,690.75 | 5,945.88 | 7,050.00 |
| Fertilizer expense | 663.88 | 858.50 | 602.00 | 264.75 |
| Carrots sold | 38.25 | 49.25 | 45.13 | 52.38 |

All sixteen matches completed normally, with zero failed worker actions, zero candidate stderr turns and a maximum measured decision time of 103.2 ms. Terminal carried and shed inventories and overflow were zero in every match. The telemetry recorded two water deaths, five nonterminal animal escapes and nineteen terminal escapes; the latter are classified separately as endgame abandonment. Wheat harvest is reconstructed by its complete inventory balance, not requested HARVEST counts. This screen did not save full replays, so it does not establish a count of missed crop harvest deadlines from the final field state.

The corrected local transition does increase realized wheat. However, the COK gap improvement accompanies lower own cash and a larger fall in opponent cash. Changed farm occupancy changes the seeded shop path; the match result cannot be interpreted as simply selling forty extra wheat. Seyam deteriorates, including reversals in seeds 2003 and 2013. This is insufficient evidence for promotion or a claim that the competition gap has closed. Four seed clusters also cannot establish broad opponent robustness.

## Next questions and reproduction

The highest-value execution question is whether feasible annual action ordering helps on broader matched development data and interacts constructively with financing. It has a precise interpreter mechanism and clear terminal conditions. The larger production question remains how to finance useful early livestock without sacrificing the crop cohort that funds expansion. Further generic worker caps or reverse-move penalties are poorly motivated by these traces.

```powershell
.venv/Scripts/python.exe scripts/phase3_field_execution.py
.venv/Scripts/python.exe scripts/phase3_harvest.py --check
.venv/Scripts/python.exe scripts/phase3_harvest.py --output data/raw/phase3-harvest-reproduction.json
```

The diagnosis reads four saved COK replays under `reports/replays/phase3-opening-field` and writes `reports/results/phase3-field-execution.json`, including replay hashes, per-day actions, exact crop/animal cohorts and harvest events. The first command runs no new games. The screen manifest is `data/raw/phase3-harvest.json`, with executable/opponent/environment hashes, configuration, actions, losses and cash trajectories. No deployed policy was edited.
