# Daily fleet: independent evidence review

The corrected daily fleet wins **30/32 development games**, compared with **22/32** for the frozen v8 champion on the same scenarios. However, its independent Mooman extension still loses **all 16 games**. The first result is a substantial improvement against two related public references; the broader competitive target remains unmet. Neither result establishes a live leaderboard rating or satisfies the reserved validation and holdout requirements.

## Identity and comparison

The reviewed executable is `9400f9b0cdaa02d268ab9e234779d17013f2facf5f5517698bdfdb04671464b7`, built at source revision `39776583b7d9dc8ad0c766c09b16516f3d40498b`. Its saved source equals `experiments.daily_routes.build()` byte for byte. The incumbent is `64fe323936dc9494add413eb956b0294658a88efe28572332c94676c68a09325`.

Both policies use official environment **1.32.7**, interpreter `bc8a54879ef02c7ea64b8b333d6a976f0ea65c4949149d01f463f23bccee653e`, identical effective configuration, seeds **5000–5007**, and both seats. All 32 candidate scenarios are unique, complete, and match their incumbent scenario's resolved seed and opponent hash. COK is pinned at `1c7335f698692f1c7bac34913a9ededc0f736dfb2b51346a4fa59098ab471d01`; Seyam at `4c02a323b0939e8f99df69dc6c23026946b033b0d831c79216ffac0ded9c8e60`.

| Opponent | v8 wins | Fleet wins | v8 mean cash gap | Fleet mean cash gap | Paired gap gain |
|---|---:|---:|---:|---:|---:|
| COK | 6/16 | 14/16 | −$4,602 | +$15,561 | +$20,163 |
| Seyam | 16/16 | 16/16 | +$21,277 | +$29,532 | +$8,255 |

With equal opponent weights and draws worth half a win, the match-score gain is **25 percentage points**, with a seed-block bootstrap 95% interval of **6.25–43.75 points**. Mean cash-gap improvement is **$14,209**, interval **$7,048–$21,875**. The 20,000 bootstrap resamples preserve both seats and both opponents within each seed. These intervals describe variation over this development panel; they do not correct for previous candidate selection or uncertainty about opponent coverage.

The COK result deserves care: the fleet's own average cash increases by $4,961, while COK's decreases by $15,202. Against Seyam, our cash increases by $20,577 and the opponent's by $12,322. Production and selling affect both players, and changed farm occupancy also changes subsequent weed/shop random-number consumption. The COK decline is therefore not proof of intentional market denial.

## Independent challenge: the remaining Mooman gap

The same frozen fleet was subsequently tested against Mooman on seeds 5000–5007 in both seats. Mooman's entrypoint is pinned at `4332662941c5eb6cb79c8d0acdb75ddf0d9c2ad66a7cb002787d3b99ffe19ded`, with its runtime bundle recorded in the experiment manifest. Candidate and incumbent games have matching opponent hashes, effective configuration, environment and resolved seeds.

| Opponent | v8 wins | Fleet wins | v8 mean cash gap | Fleet mean cash gap |
|---|---:|---:|---:|---:|
| Mooman | 0/16 | 0/16 | −$24,383 | −$21,957 |

The paired mean gap change is +$2,426, but its seed-block 95% interval spans **−$7,935 to +$14,347**. There is no convincing evidence that this policy solves the independent matchup. This extension is reported separately; it does not silently change the original two-opponent weights. The fleet should remain an experimental candidate pending meaningful progress against this strategy family.

## What changes first

The COK seed-5000 seat-0 replay identifies a concrete opening failure in v8. On day 1 it collects four manure units along a long route and deposits them only at hour 12. The hiring window ends at hour 8, so v8 hires nobody that day.

The fleet collects at hour 0, deposits at hour 1 and sells one fertilizer unit at hour 2. Cash reaches $139; it hires five hands at hour 3 and a sixth at hour 7. It also buys two melon seeds at hour 7. The opening difference is financing usable labor while hiring remains possible.

This does not immediately maximize every asset. At the end of day 7, the fleet has 12 strawberry plants versus v8's 24 in that replay. By day 14 both have roughly 43, while their animal compositions differ: fleet 16 cows and two sheep; v8 nine cows, four sheep and five geese. Existing investment formulas respond to different cash, asset and market trajectories. The experiment tests a complete executable policy; its gain cannot be attributed solely to shorter routes on an identical farm.

Eight representative replays, covering both policies against COK and Seyam on seeds 5000 and 5007 in seat 0, have their unit and market phases independently reconstructed. All **11,504 bilateral cash transitions** match the recorded balances. Their milestone ledgers and cohort counts are saved in the diagnosis data.

## Throughput and remaining labor waste

The following are realized actions averaged over 16 games per opponent. Productive actions exclude movement, pickups, deliveries and PASS.

| Opponent / policy | Movement actions | Productive actions | PASS | Wages |
|---|---:|---:|---:|---:|
| COK / v8 | 4,174 | 2,357 | 741 | $8,041 |
| COK / fleet | 3,357 | 2,452 | 1,476 | $7,980 |
| Seyam / v8 | 4,225 | 2,339 | 718 | $8,022 |
| Seyam / fleet | 3,344 | 2,434 | 1,505 | $7,931 |

Travel falls 20–21%, and productive work increases about 4%. Strawberry sales increase from 4,141 to 4,796 units against COK and from 3,963 to 4,862 against Seyam. Fertilizing also increases while fertilizer purchases decrease. These changes support a service-efficiency mechanism, although commodity prices and farm composition prevent treating action counts as a controlled economic ablation.

Much of the recovered time becomes PASS. Wages barely fall because hiring still follows the incumbent workload proxy. A labor model calibrated to this fleet, with startup and mandatory production service protected, is more informative than applying the previously rejected labor model unchanged.

## Escapes: deliberate exclusion and unresolved service failures

The fleet records **92 nonterminal animal escapes**, versus eight for v8. It records no water deaths, compared with ten for v8, and two overflow units, compared with zero. All fleet nonterminal escapes occur on days 18–27.

The diagnosis recomputes the frozen feed-value threshold at the recorded dawn, noon and last-action observations for each escaping animal:

- **62** have nonpositive feeding value at all three checkpoints.
- **72** have nonpositive value at the last action; these meet the policy's economic-exclusion condition.
- **20** still have positive value at the last action.
- **13** have positive value at dawn, including animals whose value subsequently falls.

Economic exclusion is a description of policy behavior, not proof abandonment maximizes final cash. Conversely, a positive late quote does not prove a rescue remained feasible. Most of the 20 positive late cases recover in value after earlier market saturation. The three snapshots do not prove the threshold stayed negative or positive throughout intervening hours.

One actionable witness appears in COK seed 5007, seat 0. The cow at `(9, 4)` on day 23 has positive feeding value at dawn but receives no feed reservation. At hour 8, a worker carrying three wheat units approaches it on a manure-collection route; that route then continues into harvesting, planting and watering. The cow's modeled value falls and later recovers, but it escapes. The cow at `(2, 6)` the following day also never receives a feed reservation. Replaying the policy sequentially on all 719 recorded observations reproduces every original action, so these are policy decisions rather than a lost-memory audit artifact.

The smallest useful next intervention is a limited rescue rule for previously unfed animals when carried feed is already at the animal, or a separate one-action feed bundle near a deadline. Compare the saved value with forgone work and future feed obligations; do not simply force survival for all uneconomic livestock.

## Runtime, reproducibility and deployment

All 32 games finish normally. The fleet reports **46 visible wall-budget fallbacks over 23,008 decisions** (0.20%); maximum recorded action runtime is **266 ms**, below the declared 500 ms local gate and official one-second limit. The 512-insertion limit bounds ordinary search, while a 65 ms wall deadline can still change decisions under contention.

Two independently loaded policies—source and the official loader's packaged artifact—produce identical actions on all **719 consecutive observations** of COK seed 5000, seat 0. Every action also matches the saved match. Neither execution hits a wall fallback. This verifies stateful parity on that trajectory, not unconditional determinism under different CPU loads. The COK seed-5007 trace also reproduces all 719 recorded actions.

The compact benchmark saves fallback counts, not their exact decision indices. Its replay does not contain stderr logs. Consequently, fallback steps cannot be retrospectively isolated in every game; future runs should retain indexed fallback diagnostics. A separate budget ablation at **150 ms**, retaining the deterministic insertion limit, is a reasonable next check for more headroom. It would be a new artifact and must be screened and profiled before promotion. The reviewed hash must remain unchanged.

The source reads the current public farms, shops and market and its own private inventory. Stored plans contain observed episode state and disposable reservations. No reference action tape, future realized randomness, opponent private inventory or repository-only runtime dependency appears in the artifact. Local lifecycle tests support persistent Python execution and disposal; actual hosted persistence and ladder performance remain unverified.

## Reproduction and limits

The compact evidence is [breakthrough-fleet-diagnosis.json](results/breakthrough-fleet-diagnosis.json). Input manifests are `data/raw/breakthrough-fleet-corrected.json` and `data/raw/breakthrough-season-screen.json`; their hashes, exact artifacts, opponent identities, escape witnesses and representative replay hashes are retained in the diagnosis. The broader score report can be rebuilt with:

```powershell
python scripts/breakthrough_report.py --input data/raw/breakthrough-season-screen.json data/raw/breakthrough-fleet-corrected.json --output data/interim/fleet-comparison.json
python -m pytest tests/test_daily_routes.py tests/test_runtime_state.py
```

The next selection evidence must address the demonstrated Mooman deficit, use additional development seeds for interaction tests, and subsequently use untouched validation. Seeds 5000–5007 are known development data. The two remaining COK losses are seed 5000 seat 1 (−$15,522) and seed 5007 seat 0 (−$5,818). Neither the strong original aggregate nor the selected illustrative wins remove those weaknesses. The labor-cap and expanded-cereal variants remain pending experiments; no result is attributed to them here.
