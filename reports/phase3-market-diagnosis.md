# Phase 3: inventory timing against COK

Late inventory retention has plausible value; delaying opening receipts does not look attractive in this diagnostic. The strongest examples are tomato scarcity and recovery after a wool production glut. Merely waiting for the next shop consumption offers much less headroom.

## Evidence and scope

Four saved official replays against pinned COK were inspected: seeds 0 and 2001, both seats, using `startup_fert_reserve10`, executable SHA-256 `febe9c76051a11e9ea7700e2d4701722e98274c51c50874ad03e1088b9398d4b`. This is the ten-hand startup variant, not the twelve-hand startup baseline. Their selling implementation is the same. COK's executable hash is `1c7335f698692f1c7bac34913a9ededc0f736dfb2b51346a4fa59098ab471d01`.

The analysis reconstructed worker actions and official market execution for all 2,876 transitions, reproducing recorded cash exactly. The interpreter is `kaggle-environments==1.32.7`, SHA-256 `bc8a54879ef02c7ea64b8b333d6a976f0ea65c4949149d01f463f23bccee653e`. Replays are under `data/raw/phase3-opening-diagnostic-replays/`; local diagnostic output is `data/raw/phase3-market-diagnosis.json`.

For each realized non-input sale, an **offline isolated-sale oracle** searched subsequent recorded prices up to 72 actions later, excluding terminal observation 719. It repriced every unit through the official price function and screened for sufficient storage and cash along the unchanged recorded trajectory: all carried goods plus shed contents plus the retained lot at most 100; cash less the original sale receipt at least 500.

This uses future realized prices and is **not a deployable policy or a causal counterfactual**. Independently favorable retentions overlap; their gains cannot be added into an achievable total. Withholding sales would also change future market inventories, opponent reactions, and investment. The table is an envelope of isolated opportunities under the original trajectory, not a forecast of final cash improvement.

| Seed / seat | Days 0–9 isolated gains | Days 10–19 isolated gains | Days 20–29 isolated gains | Entire-game gains allowing only four-action delays |
|---|---:|---:|---:|---:|
| 0 / 0 | 0 | 514 | 5,825 | 173 |
| 0 / 1 | 0 | 432 | 8,094 | 436 |
| 2001 / 0 | 0 | 996 | 7,685 | 309 |
| 2001 / 1 | 0 | 996 | 7,685 | 309 |

There were only four premium-product sale events in the opening of each game. Zero opening headroom therefore applies to this small constrained diagnostic, not every conceivable opening sale decision. Seed 2001 produces identical examined sale trajectories in both seats; those rows are not independent evidence.

## Observable signals behind the largest opportunities

At seed 0, seat 0, step 624, six tomatoes sold for 1,496. Their isolated best later quote added 449 after 69 actions. Cash was 64,532 and combined shed/carried goods totaled 33. The policy's existing forecast, computed only from that observation, projected next-day tomato prices of 258, 292, and 332, versus a current quote of 254. Three already-unlocked farmers markets and one pizza shop supplied an observable demand signal.

At seed 2001, step 590, four wool sold for 84. The isolated later improvement was 500 after 63 actions. Current price was 31; the legal existing daily forecast was 86, 130, and 113. A yarn store was already unlocked. Cash was 59,987 and combined goods totaled 30. Nearby step 592 sold three wool for seven total coins despite a legal next-day forecast of 64. These are examples of production-driven saturation where a modest reserve can plausibly outperform immediate liquidation.

These observations support testing a bounded overnight reserve. They do not justify three-day clairvoyant holding, broad threshold search on these four games, or a claim that the current daily forecast is calibrated for trading.

## Interpreter and policy findings

The startup policy sells all available premium goods each turn. `sell_batch=100` is effectively unrestricted in a 100-unit shed. Wheat and fertilizer have separate service reserves. Investment forecasts are calculated after the sell orders and therefore cannot currently influence retention.

Official market execution processes order indices in sequence, with unit prices quoted simultaneously for both players at each index. There are ten order slots. Selling a contested product earlier can matter when the opponent has another order first, but fixed product order alone is not evidence of a large loss. Town demand executes **after** the market: existing shops consume every four actions, and the town center every 24. Single-product shops consume two units per event; each duplicate shop consumes independently. A sale following consumption captures the resulting price rise, subject to intervening rival supply.

Current public farms reveal production and held field goods. Opponent private shed contents and future shop draws are unavailable. Forecasting must not read either from replays. The existing forecast's expected future shop composition is a modeling assumption, not future realized information. It also forecasts prices for production investment; its averaged output should not directly substitute for a one-day trading forecast.

The final executable opportunity is step 718. Terminal observation 719 is not an additional sale opportunity. Overnight inventory drops share the 100-unit shed limit, so retention must count carried inputs and harvests, maintain input purchasing capital, and force final liquidation.

## Bounded experiment

`scripts/phase3_market.py` builds an isolated candidate from the exact ten-hand snapshot. It exposes the existing observation-only forecast's next-day market inventory, quotes retained units with their own price impact, and adds a four-unit unknown-supply stress margin. It preserves wheat/fertilizer service buffers, requires working capital for two days of feed and labor plus twelve fertilizer units and 1,000 cash, and leaves forty shed slots beyond current shed and carried goods.

Retention is capped at twelve units across all products. Only even days from day 20 onward admit reserves; the following odd day sells unconditionally. This bounds retention to at most one day without episode memory or perpetually renewed deadlines. Day 29 always liquidates. Fractional remaining-day interpolation is deliberately simple and remains a model limitation: production arrives in events rather than uniformly.

The predeclared screen is eight games: COK and Seyam, seeds 0 and 2001, both seats. It compares actual final cash and reliability against the exact startup10 incumbent. Oracle figures above are kept separate from deployable results. The mechanism should be rejected if realized gains fail to justify its additional inventory risk.

## Realized screen: reject this candidate

The exact executable was `26e0495cc600c2b7a5d7a89007510936b07847cf554dcf4396f9e739db4e9888`. All eight games completed normally, but the improvement was too small to justify adopting another policy component.

| Opponent | Baseline wins | Reserve wins | Mean own-cash change | Mean cash-gap change |
|---|---:|---:|---:|---:|
| COK | 2/4 | 2/4 | +110.00 | +116.50 |
| Seyam | 4/4 | 4/4 | +64.50 | +64.25 |

Five games had exactly unchanged final cash. The other changes were +440 against COK seed 0 seat 1, and +95/+163 against Seyam seed 2001. Feed and fertilizer purchase quantities were unchanged in every game. Sale quantities were unchanged except one fewer strawberry sold against Seyam seed 2001 seat 0. This is not evidence for a match-strength improvement, and two development seeds do not support a useful generalization claim.

There were no candidate or opponent errors, no stderr turns, no measured overflow, and zero terminal shed/carried inventory in all eight games. Maximum decision runtime was 104.321 ms; the largest per-game p99 was 10.198 ms. These are local runtime observations. Price probes checked 117 official quotes and five admission/liquidation constraints; Ruff passed.

Applying the legal admission calculation to the original four COK replays explains the weak result: it would retain goods at only one of 864 examined late-game observations, step 672 in seed 0 seat 1. At the illustrative seed 2001 step 590, the full next-day forecast reduced wool inventory from 10,054 to 10,044.4. However, only ten actions remained until forced liquidation; interpolation, existing carried wool, and the supply stress reserve erased the projected net gain. The large offline opportunity required approximately 2.6 days, outside this experiment's one-day limit.

Keep startup10 unchanged. The useful conclusion is narrower than “market timing does not work”: a cautious, stateless overnight reserve rarely acts and does not capture the longer supply-recovery opportunities. A future trading experiment would need persistent lot ages, multi-day production arrival scenarios, and joint storage allocation, together with an explicit reason to prioritize that complexity over production improvements.

Complete manifests and paired quantities are saved in `reports/results/phase3-market.json.gz` and `reports/results/phase3-market-summary.json`. Reproduce the candidate and screen with:

```sh
python scripts/phase3_market.py --probe
python scripts/phase3_market.py --workers 2
```
