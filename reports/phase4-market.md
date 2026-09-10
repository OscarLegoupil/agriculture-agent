# Immediate delivery sales after failed confirmation

The phase-3 challenger passed most confirmation checks but won only 41/128 COK games, below the declared 40% floor. That validation set is now known development data; the untouched holdout has not been used. The market intervention below improves two COK outcomes in its bounded development screen without losing a Seyam game. It is promising, not a confirmed release.

## The observable opportunity

COK's reviewed controller explicitly advances its own scheduled premium sales to an earlier turn when no town consumption is due. Its more specialized layers use public farm similarity and its own future action schedule, rather than opponent private inventory. Seyam selects market experts daily while its active physical route remains fixed. These mechanisms were reviewed in [the policy-class diagnosis](phase3-policy-class.md); their source pins and attribution remain unchanged.

The useful general discriminant is **the public market clock and executable delivery**, not a guessed opponent identity. The current challenger builds market orders from the starting shed, then chooses worker actions. Away from the final day, a DROP usually leaves fresh premium products unsold until the following action. That creates a sale opportunity one turn later than the interpreter requires.

Official worker actions execute before market orders. Premium products cannot be bought from the market, and prices decrease with supply. When neither the town center nor an already-unlocked shop consumes that product this turn, advancing a feasible sale avoids exposure to another turn's rival supply. This is a local price argument, not a guarantee about final game cash: order interactions, working capital, subsequent investment, and opponent responses can change the trajectory.

The rule consults only our own current inventories and chosen actions, shared market timing, and already-observed shops. It does not use seeds, opponent names, hidden inventories, future draws, or observed future actions.

## Distinct from previous rejected experiments

The [overnight reserve](phase3-market-diagnosis.md) acted at only one of 864 inspected late-game COK observations and failed to improve match results. It exposed a much longer wool recovery opportunity but did not capture it. Broad delivery deferral and selective deposits also failed their earlier screens; saving a DROP did not reliably turn into productive work.

This intervention changes neither return routes nor holding horizons. It sells goods that the existing scheduler already delivers. It does not repeat the animal-price scenario model or tune another selling threshold. The only timing exception is explicit: if current town consumption can raise the product's price before the next market opportunity, retain the existing next-turn sale behavior.

## Implementation and contracts

[`scripts/phase4_delivery.py`](../scripts/phase4_delivery.py) builds the isolated candidate from exact v8 snapshot `64fe323936dc9494add413eb956b0294658a88efe28572332c94676c68a09325`.

The finalizer projects shed transfers in actual worker order. An earlier PICKUP can free space; a later PICKUP cannot rescue an earlier overflowing DROP. Partial deposits follow inventory insertion order. A worker moving toward shed access does not count as a delivery. Animal placement and shed placement are distinguished. Input deposits still consume storage, but wheat and fertilizer are never included in additional sales.

Existing market order positions are retained, including feed and other purchases. An existing premium sale can be enlarged only to cover genuinely deposited goods; otherwise a sale is appended only if a market slot is free. The final day retains the already-tested terminal controller unchanged. Planning never spends these receipts before they execute.

Seven interpreter-backed tests cover same-turn DROP/sale, finite storage, pickup/drop ordering, town consumption after the market, preserved input orders and market limits, non-delivery movement, and animal-input storage. All pass; Ruff passes. The built artifact remains self-contained and deterministic.

On four saved seed-3000 v8 trajectories, the legal finalizer identifies the following opportunities:

| Opponent / seat | Turns with additional eligible sales | First opportunity |
|---|---:|---|
| COK / 0 | 89 | Step 155, five wool, 228 cash |
| COK / 1 | 87 | Step 155, five wool, 228 cash |
| Seyam / 0 | 68 | Step 155, five wool, 216 cash |
| Seyam / 1 | 64 | Step 155, five wool, 415 cash |

These are observation-only eligibility counts on the baseline's chosen actions. They are not incremental sale quantities over a season or additional revenue. Their timing shows that capital availability before later cohorts can change, not just late-game liquidation.

## Fixed sixteen-game screen

The declared panel is COK and Seyam, seeds 3000, 3017, 3042 and 3063, both seats. These scenarios are now development data. The baseline uses the exact matching v8 validation records. Environment, configuration, opponent hashes and source identities were checked. The challenger SHA-256 is `9ba68bcdfba55d8fec2a0aeb6486fe6a0a191a210b798e354eaa9d24f83e0f8d`.

| Opponent | v8 wins / games | Delivery candidate wins / games | Mean own-cash change | Mean cash-gap change |
|---|---:|---:|---:|---:|
| COK | 4/8 | 6/8 | −3,719.00 | +4,425.38 |
| Seyam | 8/8 | 8/8 | +14,538.13 | +7,936.13 |

The two converted COK games are both seats of seed 3063: a deficit of 7,881 becomes a lead of 6,698. Those two outcomes are correlated, not two independent confirmations. COK seed 3017 still loses in both seats, with worse gaps. No attempt was made to stop the fixed screen after a favorable result.

All sixteen games finish normally, with zero stderr turns, zero measured overflow, and zero terminal carried or shed inventory. Maximum action time is 52.539 ms; the largest per-game p99 is 2.470 ms. Five nonterminal animal escapes are recorded across the candidate panel, so this result does not establish perfect scheduling.

## Why this is not simply extra market income

Eleven of sixteen games develop different observed shop paths from the baseline, first diverging on days 9, 12 or 18. Changed planting and empty-tile states can change the official environment's random-call sequence before later shop draws. Both policies still use the same declared seed; the paired result measures their whole-game effect, not an intervention under identical future shop outcomes.

For example, Seyam seed 3000 seat 0 changes its day-20 herd from ten cows/two sheep/six geese to eight cows/ten sheep, while COK seed 3000 shifts toward geese. Against COK the candidate's own mean cash falls while the opponent's falls more. Against Seyam it rises substantially. These differences prohibit attributing the full cash-gap change to one-turn price capture.

The correctly limited conclusion is that immediate executable sales are a materially active mechanism with an encouraging matched screen. A broader predeclared development panel should test whether the benefit survives additional demand paths and whether it interacts with production-capacity changes. It has not passed a fresh promotion gate and makes no leaderboard claim.

## Reproduce

The subsequent 64-game check on known seeds 3000–3015 rejects standalone
promotion. Seyam improves from 29/32 to 30/32 wins (mean gap +15,821.63 to
+18,090.75), but COK falls from 12/32 to 10/32 (−3,706.97 to −4,343.56).
The encouraging four-seed result did not generalize across this broader
development panel. Preserve the candidate as an experiment; do not extrapolate
its converted seed-3063 wins into a competitive improvement.
[Complete broader records](results/phase4-delivery-field.json.gz).

```sh
python -m pytest tests/test_phase4_delivery.py -q
python scripts/phase4_delivery.py --diagnose-replays reports/replays/phase3-validation --output reports/results/phase4-delivery-opportunities.json
python scripts/phase4_delivery.py --workers 4 --output data/raw/phase4-delivery-repeat.json
```

The screen driver refuses to overwrite an existing experiment file. Complete results are [archived](results/phase4-delivery.json.gz), with [matched outcomes and cash changes](results/phase4-delivery-summary.json), [opportunity counts and replay hashes](results/phase4-delivery-opportunities.json), and the exact candidate under `reports/sources/`.
