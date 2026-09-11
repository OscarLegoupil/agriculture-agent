# Why the current public frontier beats v8

The newly qualified public Shop Router 0909 opponent exposes a larger execution gap than the earlier COK panel. In the two seed-5000 losses, v8 finishes at 70,915 and 54,508 coins against 92,920 and 78,038. The principal differences are repeatable production routes, a much smaller wage bill, and earlier melon sales. These two games diagnose mechanisms; they do not estimate a field win rate.

The incumbent is the frozen `64fe3239…c68a09325` artifact. The opponent is [Mooman's Shop Router 0909 K6 package](https://github.com/mooman0222/Kaggriculture-opencode/tree/b7a0aad0b6047d61e64885966cdb76abf2d22021/agents/sr0909_live), with main-file hash `43326629…ffe19ded` and separately pinned router/action-table hashes. Its public submission 56156691 had 65 wins in 97 returned completed public episodes and a latest rating of 2697.67 at September 11, 11:07 UTC. That observation establishes a current competitive reference, not a rank prediction for our agent. This opponent shares public route ancestry with existing challenges; it does not increase the number of independent strategy lineages.

## The cash gap reconciles exactly

The existing official-transition ledger reconstructs worker actions and both players' market orders on copies of each recorded preceding state. All 2,876 player-cash checks match. No policy is rerun and no future randomness is sampled. The compact [diagnosis result](results/breakthrough-frontier-diagnosis.json) preserves replay hashes, ledgers, daily checkpoints, and service measurements.

| Mooman advantage in final cash | v8 seat 0 | v8 seat 1 |
|---|---:|---:|
| Wheat receipts less bought feed and wheat seeds | 13,970 | 13,329 |
| Lower wages | 4,308 | 4,308 |
| Fertilizer receipts less purchases | 3,923 | 3,587 |
| Melon receipts less seeds | 3,696 | 3,696 |
| Strawberry receipts less seeds | 2,467 | 4,670 |
| Milk receipts | 5,776 | 2,760 |
| Wool receipts | −8,412 | −8,504 |
| Tomato receipts less seeds | −7,117 | −3,603 |
| All remaining costs and receipts | 3,394 | 3,287 |
| **Final cash gap** | **22,005** | **23,530** |

These are accounting differences, not additive counterfactual gains. More wheat changes both players' prices, and additional animals consume capital and worker time. The result also includes an exact symmetric quantity/realized-price decomposition of each commodity's sales; its terms describe the observed revenue difference and do not identify the causal value of a scheduling change.

## Where the programs diverge

Both farms finish day 0 with twelve melons, seven wheat, two cows, and two sheep. By day 2 Mooman has placed a third cow while v8 has planted two additional melons. Mooman adds a fourth cow on day 3; v8 retains its two-cow/two-sheep cap until day 8. V8 buys land on day 4, Mooman on day 6. The later animal ramp therefore competes with a larger berry commitment and a tighter feed budget.

| Completed day, seed 5000, v8 seat 0 | v8 | Mooman |
|---|---|---|
| 5 | 4 berries, 7 wheat, 2 cows, 2 sheep | 4 berries, 3 wheat, 4 cows, 2 sheep |
| 8 | 22 berries, 5 wheat, 2 cows, 6 sheep | 20 berries, 5 wheat, 8 cows, 4 sheep |
| 11 | 29 berries, 6 wheat, 2 cows, 8 sheep, 1 goose | 33 berries, 20 wheat, 8 cows, 6 sheep, 3 geese |
| 14 | 43 berries, 7 wheat, 2 cows, 14 sheep, 2 geese | 33 berries, 24 wheat, 8 cows, 6 sheep, 3 geese |
| 26 | 19 berries, 12 wheat, 11 carrots | 13 berries, 16 wheat, 29 carrots |

The ripe opening has an additional execution race. Mooman starts harvesting melons at day 10, hour 5; v8 starts at hour 10. Mooman's first sale executes at hour 9 using that turn's delivery, and it sells sixty melons by hour 15. V8 first sells at hour 17, then carries twenty-four units through the nightly transfer. Mooman realizes 227.67 coins per melon over seventy-two units; v8 realizes 153.05 over eighty-four. The twelve extra melons do not recover the lost execution price.

This motivates a complete early-maturity pipeline: fertilizer before the maturity day, the resulting capped harvest at dawn, prompt delivery, and sale against the projected same-turn shed. Raising a sale threshold alone cannot advance a harvest still in the field. Its fertilizer and labor costs must be included in the full-game comparison.

## Worker efficiency is a larger opening than more workers

| Realized or located measure, seed 5000, v8 seat 0 | v8 | Mooman |
|---|---:|---:|
| Worker turns | 7,567 | 6,643 |
| Productive actions changing official state | 2,340 | 3,066 |
| Movement actions | 4,181 | 2,782 |
| PASS | 700 | 402 |
| Immediate movement reversals | 50 | 12 |
| Wage expense | 7,938 | 3,630 |
| Wheat harvested | 182 | 517 |
| Successful wheat harvests | 59 | 162 |
| Fertilizer still uncollected at nonterminal day end | 76 tile-days | 3 tile-days |

The comparator grows almost three times as much wheat with fewer paid worker turns. It is not merely harvesting wheat earlier: the harvested age distributions overlap, and both use ages 2–4. Its repeated planting and service routes turn substantially more of the existing land into completed rotations.

Fertilizer provides a second direct scheduling signal. The day-end count uses the official final worker actions before refresh and excludes days after 26. A remaining available unit is lost collection capacity when the next day again offers only one unit. These 76 versus 3 opportunities are not all profitable after travel, but they show why animal count alone cannot explain the fertilizer gap. V8 also returns 102 fertilizer units and 81 wheat through ordinary DROP actions, against Mooman's 30 and 35; these are returned inputs, not destroyed resources.

Cow care is already near its cohort bound. Keeping v8's observed animal placements fixed, ideal feeding and care increases milk from 72 to 72 units in both cases. Wool increases from 272 to 324 units in seat 0 and 276 to 320 in seat 1; perfect care only on actually fed days reaches 281 and 283. The larger missed wool opportunity is feeding and usable service capacity, not another general care priority increase. These are optimistic fixed-cohort bounds with immediate collection and no labor charge.

Berry fertilization is more efficient in the reference: on the first replay, 119 of 131 observed production events receive a fertilizer bonus, versus v8's 95 of 169. No held-yield cap loss occurs at those measured events. V8 owns more berry tiles but sells only eight more berries. This suggests improving application timing and routes before interpreting a larger berry footprint as effective production capacity.

## Long holding is not the main explanation in these losses

Mooman does hold premium goods longer after collection: inventory-turns divided by sold units is about 21 turns for strawberries and 17.5 for wool, against v8's 9.4 and 6.0. This stock-residency measure includes carried goods and is not a measured market-only waiting time. It does not establish a multi-day hoarding advantage. Mooman's melon residency is shorter, 4.7 versus 6.5 turns, while milk earns a lower realized average price despite greater volume.

The highest-value tests are therefore the already implemented service-route alternative, the finite-stock selling alternative as a separate hypothesis, and a complete melon-maturity/delivery race. The broader season calendar must earn its place through realized rotations and wages. The earlier blanket herd ramp cannot be rehabilitated merely by pointing to Mooman's final animal counts.

Reproduce the bilateral ledger by calling `scripts.phase3_field_economics.analyze(path)` and the action/service measurements through `scripts.phase3_field_execution.analyse(path)` and `scripts.phase4_execution.service_decomposition(replay)` on the two hashed seed-5000 replays under `reports/replays/breakthrough-frontier/`. Raw replay-derived detail remains in ignored `data/raw/frontier-20260911/mooman-loss-diagnosis.json`. This analysis used the pinned `kaggle-environments==1.32.7` interpreter with SHA-256 `bc8a5487…cee653e`.
