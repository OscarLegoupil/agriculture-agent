# Execution after the release validation failure

The frozen v8 artifact `64fe323936dc9494add413eb956b0294658a88efe28572332c94676c68a09325` failed the COK family floor: 41/128 wins and a mean cash deficit of roughly 4,528. The completed 3000-3063 panel is now known development evidence; it is not reused as fresh validation. The reserved holdout remains untouched.

## Diagnosis separates execution from production regimes

The original four recorded COK games, seeds 3000/3001 in both seats, were all wins. Four subsequent reproductions of existing losses, seeds 3029/3063, supplied the missing contrast. This is a deliberately selected diagnosis set, not a representative sample.

Across all 128 COK records, losing games actually have higher own cash than winning games (81,491 versus 78,162), similar worker-action counts and fewer escapes per game. Losses average 11.82 cows, 4.03 sheep and 2.16 geese purchased; wins average 6.00, 8.27 and 3.78. Losing games earn more milk and less wool. Those associations identify vulnerable production regimes; they do not prove that changing the herd mix causes a win.

| Recorded seat-0 match | Cash gap | Own/COK productive actions | Own/COK movement | Own/COK worker actions | Own terminal field quote value |
|---|---:|---:|---:|---:|---:|
| 3029 | -21,530 | 2,373 / 2,711 | 4,214 / 3,366 | 7,593 / 6,917 | 594 |
| 3063 | -7,881 | 2,359 / 2,564 | 4,199 / 3,625 | 7,594 / 6,914 | 429 |

Productive actions exclude travel, waiting, pickup and product delivery and require an actual official state change. The terminal field number multiplies held units by the final quote; it ignores price impact and collection feasibility and is an upper bound on readily identifiable stranded value. Both losses have zero carried/shed terminal inventory, zero overflow and no nonterminal escapes. They also have no recorded crop water deaths. The two water deaths in winning seed 3000 and one in winning seed 3001 are real irrigation misses, not exhausted-crop abandonment. Neither terminal cleanup nor an escape-count fix can by itself explain the large losses.

## A first missed feeding day destroys production

The earliest identified material service failure in seed 3029 occurs on day 8: the initial sheep at (4, 0) reaches its production eve with three banked care units but is not fed. It survives because this is only its first missed feeding day, yet the official refresh discards the banked bonus and produces one wool instead of four. There are seven such missed sheep production eves in this replay, losing eighteen immediately banked wool units. Subsequent care accumulation also suffers on other missed feeding days.

We replay the official daily animal transition on recorded placement cohorts and actual end-of-day feed/care flags, removing holding limits with immediate hypothetical collection. This is an offline service decomposition, not a free, deployable production plan.

| Seed 3029 wool | Own | COK |
|---|---:|---:|
| Actual harvested | 192 | 270 |
| Actual feeding/care, immediate collection | 192 | 270 |
| Care on every actually-fed day | 203 | 271 |
| Ideal feeding and care on the same placement cohorts | 254 | 272 |

No wool holding-cap loss is needed to explain the recorded deficit: actual service plus immediate collection reproduces actual harvest exactly. Extra CARE on already-fed days recovers only eleven units. The remaining 51-unit difference requires better feeding and the care it enables. Sheep miss 32 nonterminal feeding days; COK sheep miss one. The initial hypothesis that simply pricing CARE above its fixed value of 60 would address the main problem was therefore rejected before implementation.

In seed 3063, the same decomposition gives own wool 118 -> 120 -> 138 and milk 222 -> 224 -> 234. COK produces all 120 possible wool and all 279 possible milk on its recorded cohorts. Earlier productive investment still contributes to that milk gap.

## Two bounded feed interventions

Both candidates extend the existing route-deadline prepass, preserving current observations, pickup costs, stock reservations and feasible arrival-plus-FEED timing. Neither changes CARE pricing or reads future realized state.

- **Daily obligations:** every currently useful, unfed animal can trigger the deadline prepass. This investigates care lost on nonproduction days as well as immediate bonuses.
- **Banked production:** besides escape risks, admit a current production-eve task only when the banked bonus that fits the holding cap, valued at the observed product price, exceeds one wheat plus the existing action charge. This targets immediate, valuable losses.

The common predeclared screen is COK/Seyam, seeds 3000, 3017, 3042 and 3063, both seats: sixteen games per candidate. Seed 3029 supplies diagnostic evidence, not a substituted screening seed.

The initial 32 games exposed a priority defect: mixing new healthy-animal obligations into a list sorted only by route slack could allocate the scarce worker/feed to a healthy animal before an already-once-unfed animal. The daily variant recorded 25 nonterminal escapes. A constructed official-state test reproduces that conflict: the old version walks toward the healthy animal; the corrected version rescues the sheep one feeding from escape.

An explicit 32-game correctness extension preserves escape-risk priority before considering the new obligations, then retains the original slack ordering within each tier. This is not an unrecorded parameter search. Original snapshots remain reproducible with `--priority slack`.

| Variant | COK score | COK mean gap | Paired COK gap change | Seyam score | Seyam mean gap | Paired Seyam gap change |
|---|---:|---:|---:|---:|---:|---:|
| Frozen v8 on this panel | 4/8 | -1,744.75 | -- | 8/8 | +7,646.13 | -- |
| Daily, initial priority defect | 2/8 | -13,195.38 | -11,450.63 | 5/8 | +2,461.75 | -5,184.38 |
| Banked, initial priority defect | 4/8 | -2,452.38 | -707.63 | 8/8 | +8,918.25 | +1,272.13 |
| Daily, escape first | 3/8 | -7,670.00 | -5,925.25 | 7/8 | +7,960.63 | +314.50 |
| Banked, escape first | 4/8 | -2,087.50 | -342.75 | 8/8 | +9,480.88 | +1,834.75 |

Daily escape-first reduces its early escapes from 25 to four, but still harms the COK matchup. Banked escape-first records one early escape and ten water deaths across its sixteen matches. Its equal-opponent mean gap improves only 746 cash with no score improvement. Neither result closes the competitive gap or meets a material promotion criterion. Four seed clusters are inadequate for a broad robustness claim.

## Did the corrected mechanism actually help?

In seed 3063 seat 0, banked escape-first changes wool 118 -> 119, milk 222 -> 224 and eggs 77 -> 81. Directly discarded banked units fall from eight wool/three milk/six eggs to five wool/zero milk/three eggs. Wheat expense rises from 10,283 to 10,481; there are no early escapes or water deaths. The cash gap improves modestly, from -7,881 to -7,323.

Some remaining bonus losses are rational under the observed quote: on day 17, two banked wool units are worth at most ten cash while wheat costs 43. The targeted rule deliberately declines that rescue. Day 11 is different: three banked wool units are worth 492, cash exceeds 10,000, yet shed wheat is zero through hours 8-12, one at hour 16, zero at hour 20. A production predicate alone cannot make distant carried wheat available at the needed pickup point. The purchase rule counts wheat carried anywhere against all feeding demand, so local input shortages remain possible despite adequate total inventory and cash.

The daily version changes later herd/cohort composition substantially; its larger output cannot be interpreted as a fixed-farm scheduler gain. Changed occupancy also changes seeded shop paths. All reported cash differences are whole-policy matched outcomes, not estimates obtained by multiplying recovered units by an unchanged market price.

## Artifacts, reliability and next question

The original variants are `02bee531e0e54cc0611c1a3a46a4cc5c0dd9cca8fc1d06bad012b75dd56bad2b` (daily) and `ff80cef5a4bbc8209d93f1b4bcd1131e765ac7692070c6996e0ee02ae4a54280` (banked). Corrected variants are `1333b40f73542c60931b6ae455ccaac6472b9d48a9cb09f1144bf9bf97cae839` and `401b58a64d12a3df82ae9157a8d12a0d1e99c10c273fecb96f0d399501a9c6d4`.

All 64 games completed normally with zero candidate stderr. Corrected maximum decision times were 66.1 ms daily and 61.2 ms banked. These are local measurements, not hosted guarantees. Three focused tests cover the production bonus reset, nonproduction-day exclusion and scarcity priority for both variants. The deployment remains unchanged.

The next execution hypothesis should address spatial feed availability with reserved production obligations, while charging the extra inventory and displaced crop work. Another CARE threshold or unconditional feeding boost is not supported by these results. That question must be evaluated separately from the economic allocation work; useful mechanisms should not be assumed additive.

```powershell
python scripts/phase4_execution.py
python -m pytest tests/test_phase4_feed_priority.py
python scripts/phase4_care.py --priority escape --output data/raw/phase4-care-corrected-reproduction.json
python scripts/phase4_care.py --priority slack --output data/raw/phase4-care-initial-reproduction.json
```

The diagnosis command runs no games. It reads the completed frozen-release records, eight saved original/reproduced trajectories, and available corrected feed replays; its output is `reports/results/phase4-execution.json.gz`. Screen manifests are `data/raw/phase4-care.json` and `data/raw/phase4-care-corrected.json`, with pinned sources, environment, configuration, seats, actions and costs. Corrected and original seed-3063 COK replays are retained under `reports/replays/phase4-care`.


## Spatial feed reserve counterfactual

A further 32-game extension tests the specific remaining local-input constraint, not another feeding-priority threshold. The depot rule holds at most three wheat for currently unfed animals whose pickup/feed route remains feasible after the next-turn purchase delay. It activates only before day 29 with at least 1,000 cash, retains that reserve when selling wheat, and conservatively counts all carried goods against possible shed capacity. Inputs ordered at the market are never inserted into the same-turn scheduler inventory. Two official reset-based tests, parameterized over both policies, check failed same-turn pickup, successful market arrival, sale reserve, pending cargo and the final feasible pickup window.

| Candidate | COK score | Mean gap | Paired gap change vs v8 | Seyam score | Mean gap | Paired gap change vs v8 |
|---|---:|---:|---:|---:|---:|---:|
| v8 + depot | 5/8 | +5,859.50 | +7,604.25 | 7/8 | +8,660.75 | +1,014.63 |
| Banked escape-first + depot | 6/8 | +8,132.88 | +9,877.63 | 7/8 | +7,359.75 | -286.38 |

This is an informative interaction screen on the same four known seed clusters, not fresh validation. Both candidates record two nonterminal escapes and eleven water deaths across sixteen games. All 32 games finish normally with no candidate stderr, maximum decision time 65.7 ms. Neither candidate is promoted from this small panel.

Seed 3063 seat 0 illustrates both the mechanism and the attribution limit. Depot alone yields 275 eggs, 118 milk and 93 wool; adding banked deadlines yields 283 eggs, 117 milk and 99 wool. Direct discarded bonus falls from eleven eggs/six wool to two eggs/four wool. Wheat expense rises from 10,116 to 10,441. The earlier unmodified v8 trajectory produced 77 eggs, 222 milk and 118 wool: the depot interventions change subsequent herd investment and the occupancy-coupled shop path. Own cash is 54,470 with depot and 56,161 with its banked combination, versus 59,305 originally; opponent cash falls from 67,186 to 36,817 and 40,025. The large match-gap change therefore cannot be attributed solely to recovered feed bonuses at fixed market prices. A broader matched test is needed to distinguish useful robustness from favorable path changes.

Exact candidates: depot `3f0e85ff92c2838c98e90f226ca42a5bdb0f3c2e38901d8cebb02359df78e2ac`; banked depot `ee412dabf71824ebf32c870b021bc7ae0a3cc35d231f142c8c0fc8550d09a6ba`. The completed manifest is `data/raw/phase4-depot.json`; compact official-transition diagnosis is [phase4-depot-diagnosis.json](results/phase4-depot-diagnosis.json).

```powershell
python -m pytest tests/test_phase4_depot.py
python scripts/phase4_depot.py --output data/raw/phase4-depot-reproduction.json
python scripts/phase4_depot.py --diagnose
```

The last command reuses the completed screen and saved seed-3063 replays without running games.
