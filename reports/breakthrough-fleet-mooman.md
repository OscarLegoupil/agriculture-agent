# Why the fleet still loses to Mooman

The corrected fleet remains **0/16 against Mooman**, with a mean cash gap of **−21,957**, compared with **−24,383** for v8 on the same eight seeds and both seats. Its paired gap improvement is 2,426, with a seed-block bootstrap 95% interval of **−8,269 to +14,407**. This challenge result does not demonstrate a reliable improvement. The strong COK/Seyam screen does not resolve this independent weakness.

The central finding is that the fleet has almost exhausted the available strawberry-service improvement. In the seed-5000 seat-0 loss it sells **337 of the 340 units** that its actual strawberry cohorts could possibly produce before the last sale opportunity. Mooman earns more from fewer, earlier berries and combines those receipts with a larger commercial-wheat rotation and cheaper labor. More fertilizer scheduling on the same berry cohorts cannot close this gap.

## Evidence and identities

The fleet artifact is `9400f9b0cdaa02d268ab9e234779d17013f2facf5f5517698bdfdb04671464b7`; v8 is `64fe323936dc9494add413eb956b0294658a88efe28572332c94676c68a09325`. Mooman's reviewed executable is pinned at `4332662941c5eb6cb79c8d0acdb75ddf0d9c2ad66a7cb002787d3b99ffe19ded`. Both manifests use official environment 1.32.7 and interpreter `bc8a54879ef02c7ea64b8b333d6a976f0ea65c4949149d01f463f23bccee653e`.

Seeds 5000–5007 are known development data. All 16 fleet games complete normally, with no water deaths, 66 nonterminal animal escapes and four overflow units. The median gap is −24,029; the tenth-percentile gap is −37,465. Bootstrap resampling retains both seats within each seed (10,000 draws, RNG 20260910, matching the canonical comparison summary). Its uncertainty covers this sampled field, not previous candidate selection or future opponents.

Three selected replays are reconstructed through official unit and market helpers: fleet seeds 5000 and 5007 in seat 0, plus v8 seed 5000 in seat 0. All **4,314 bilateral cash transitions** match the saved observations, and reconstructed candidate action counts equal benchmark telemetry. These are diagnostic cases, not a representative statistical sample. No new games or future random draws were generated.

## The first consequential constraint is already visible on day 5

In the seed-5000 fleet game, Mooman plants four strawberries on day 5, eight on day 6, four on day 7 and four on day 8. The fleet starts on day 6 with three, followed by nine, four and four on days 7–9. Its remaining 23 berries are commissioned across days 10–14. Mooman commissions its final 13 on day 11.

The fleet's delay is not an inability to afford four seeds:

| Recorded fleet decision | Cash and consequence |
|---|---|
| Day 3 | Replants all seven harvested wheat positions; the opening requires seven wheat before considering berries. |
| Day 5, hour 0 | Holds 1,181 cash, fourteen melons, seven age-two wheat and four animals; buys six hands for 20 and four feed units for 124. |
| Day 5, hours 1–20 | Cash remains 1,037. No berry seeds are ordered while the original quadrant remains occupied. |
| Day 5, hour 21 | Sells four delivered manure units for 370. |
| Day 5, hour 22 | The land reserve condition finally passes; spends 1,000 on land. |
| Day 5, hour 23 | Buys the first strawberry seed, which becomes usable next action. |
| Day 6, hour 1 | Plants the first strawberry. |

Mooman instead replaces four wheat positions inside its original quadrant. It pays 400 for the four berry seeds and postpones land until day 6, when early wool receipts finance expansion. It also has six animals by day 5 versus the fleet's four; this is a different investment schedule, not evidence that copying just four coordinates reproduces its economy.

The bounded opening hypothesis is therefore to exchange four ripe wheat positions for four berries on day 5, retaining three wheat and existing livestock. Buying those seeds alongside the recorded labor/feed order fits the observed cash without borrowing or assuming future sales. Four `WATER → HARVEST → PLANT STRAWBERRY → WATER` bundles require sixteen productive actions plus travel. Harvesting at two wheat units instead of waiting for four forgoes up to eight units of that current cohort, before considering subsequent rotations. Whole-day execution and next-day working capital still require a tested policy; this arithmetic is not a proven profitable opening.

## How the deficit accumulates

The following balances are after the named day's actions in the same seed-5000 game:

| End of day | Fleet cash | Mooman cash | Fleet gap |
|---|---:|---:|---:|
| 5 | 297 | 807 | −510 |
| 10 | 10,789 | 16,379 | −5,590 |
| 14 | 12,313 | 26,665 | −14,352 |
| 17 | 20,224 | 45,614 | −25,390 |
| 23 | 42,373 | 73,769 | −31,396 |
| Final | 66,645 | 92,888 | −26,243 |

By day 14, Mooman has 24 wheat and 33 berries, while the fleet has seven wheat and 43 berries. During days 15–17 the fleet replaces those seven wheat with tomatoes; Mooman maintains approximately 25 wheat. The tomatoes later earn 17,854, so replacing them with grain is a real opportunity-cost decision. Commercial wheat should be evaluated jointly with cohort timing, feed spending and available labor.

The final difference decomposes into **17,763 less income and 8,480 more expenses** for the fleet:

| Commodity or expense | Fleet | Mooman |
|---|---:|---:|
| Strawberry units sold / receipts | 337 / 27,295 | 249 / 33,146 |
| Wheat units sold / receipts | 113 / 5,525 | 279 / 13,467 |
| Purchased feed units / expense | 227 / 10,038 | 129 / 4,571 |
| Fertilizer receipts | 11,411 | 16,044 |
| Milk units sold / receipts | 298 / 17,567 | 245 / 24,008 |
| Labor expense | 8,013 | 3,630 |
| Land expense | 3,000 | 3,000 |

Fleet berries realize approximately 81 per unit versus Mooman's 133; milk realizes 59 versus 98. These are actual receipt-weighted prices, incorporating delivery timing and market impact. They do not isolate intentional market denial. Changed farm occupancy can also change later weed/shop random-number consumption, so v8-versus-fleet income comparisons do not share a fixed realized demand tape.

## What remains possible with the same assets

The official crop refresh, applied to each observed strawberry cohort with perfect watering, fertilizer and immediate collection, yields 340 saleable units for the fleet and 264 for Mooman. Actual sales are 337 and 249. At seed 5007, the fleet sells 316 of a 338-unit ideal. The v8 seed-5000 baseline sells only 257 of 338. Thus the fleet substantially fixes v8's service loss, but the residual three-unit gap in the main witness cannot explain the 5,851 strawberry-income deficit.

There is still labor capacity to reclaim. The fleet executes 3,325 moves, 2,394 productive actions and 1,590 PASS actions; Mooman executes 2,782, 3,146 and 402. Repricing each recorded fleet day's labor bill at a ten-hand ceiling gives an optimistic saving of 4,749 if every output survives. Idle time is distributed unevenly, so this is a cost ceiling, not proof two hands can be removed safely. The full-game labor ablation must decide that.

These bounds rank the next interventions: establish an earlier berry cohort without delaying essential inputs; test sustained commercial-wheat capacity and its interaction with labor; retain separate economic retirement tests for saturated livestock. Additional berry-service complexity has little headroom in the main loss. None of the bounds is additive, and none substitutes for matched official games with a reacting opponent.

## Opening counterfactuals

The day-5 fleet starts with 1,181 cash and seven occupied wheat positions. After buying six hands and four feed units it has 1,037. It waits until hour 21 to sell four fertilizer, buys land at hour 22, and orders its first strawberry seed at hour 23. Its first actual berry planting therefore falls on day 6. Mooman instead replaces four ripe wheat positions with berries on day 5.

The bounded `experiments/berry_bridge.py` prototype purchases four seeds for 400 after current labor and feed commitments, protects 200 cash, and commits four ripe northwest wheat positions to watering, harvest, berry planting and planting-day watering. It retains three wheat positions. A separate `arrival_replan` ablation discards unexecuted route reservations whenever newly hired workers become observable; already acquired inputs and completed work remain in the observation.

Official 216-action prefixes against the pinned Mooman implementation on seed 5000, both seats, give the following identical seat results. These are mechanism witnesses on known development data, not full-season results or estimates of competitive strength.

| Variant | Day-5 berries | Day-8 berries | First added land | First wool sale | Day-8 cash |
|---|---:|---:|---|---|---:|
| Fleet | 0 | 16 | Day 5, hour 22 | Day 7, hour 0 | 264 |
| Four-berry bridge | 4 | 20 | Day 7, hour 1 | Day 7, hour 0 | 2,759 |
| Arrival replan | 1 | 22 | Day 5, hour 17 | Day 6, hour 17 | 846 |
| Both | 4 | 22 | Day 7, hour 1 | Day 7, hour 0 | 924 |

All eight prefixes have zero crop deaths or animal escapes. Bridge-only retains the fleet's first 120 actions exactly. Its delayed land purchase does not displace a larger berry cohort through day 8 in this witness, but it has fewer placed cows and more cash. That difference cannot be interpreted as a cash gain without a full season. Arrival replanning advances the wool sale only without the bridge: the interaction is not additive, and the two hypotheses require separate screening.

The Mooman prefix executables have hashes `03f1f85112640b400b8971a11ce610c4bf2af93a07ba1b4573ecb1d6edcd2e33` (bridge), `6c2dcbdfb814628bb48b32206ed76fd00d6ec233858cbcf6fe81ae43924feba7` (arrival-only) and `e59eb9132e477f86fafdbe462e84133cc0cbb71a666c69c9aa63f4666e2d86f5` (both). Subsequent formatting changes the bridge and combined source hashes to `8e96f34cefc65e010d9437902ee7bc88b3a8363b05785436145167ac1a26671d` and `8160ec8bf6ec41f94f1400a30a192b85bcddfe538eceaaef4295f1fd2962dbd5`; the final contracts use these formatted versions. The candidate remains separate from the deployed policy. Twelve contracts cover both seats, cereal composition, actual planting success, input conservation after worker arrivals, clean-directory execution and process reset:

```powershell
python -m pytest tests/test_berry_bridge.py -q
```

## Reproduce

```powershell
python scripts/diagnose_fleet_mooman.py
```

The command reads the saved fleet and race/Mooman manifests and three named replays. It writes [the compact diagnosis](results/breakthrough-fleet-mooman-diagnosis.json), including source/opponent identities, replay hashes, daily ledgers, realized actions, cohort bounds and paired uncertainty. Large source replays remain outside version control.
