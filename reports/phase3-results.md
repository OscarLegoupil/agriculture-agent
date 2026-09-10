# From larger farms to executable production

The previous experimental champion (`0098d9e4…`) improved the public anchor
pool but won only 13.28% against the harder challenge pool on 64 validation
seeds. Those seeds became development data for this cycle. The unchanged v7
artifact remains the rollback; the phase-3 candidate must qualify on new data.

## What changed the outcome

Opening investment was the first constraint. A small initial herd and commercial
wheat finance melon cohorts without reserving the cost of fertilizing every
plant. Fertilizer is reserved for feasible near-term applications to recurring
crops. This makes startup cash available when planting dates still matter.

That opening alone did not solve the competition problem. Its six-seed screen
looked encouraging, but a broader 128-game development check won only 2/32 COK
games. The failed check is retained in
[its complete summary](results/phase3-opening-field-summary.json).

Three concrete replay findings directed the next experiments:

1. A four-sheep cap overruled the economic model even when wool was the better
   investment. A shared 18-animal ceiling permits meaningful species allocation.
2. Expiring annual crops were harvested before a useful final watering. The
   controller now permits WATER then HARVEST only when travel, harvest and
   terminal delivery can fit.
3. A worker carrying saleable goods could DROP before starting a feed route,
   missing the last feasible departure. A reservation pass accounts for home
   travel, pickup, destination travel and feeding. It bypasses discretionary
   delivery only when cash and storage allow it.

Manure collection is valued at its observed market price. Joint worker
assignment still handles ordinary tasks; the deadline pass reserves critical
workers, destinations and shared feed first. The production bounds are three
quadrants, 50 crops, 12 hired hands and 18 animals. They are capacity limits,
not instructions to buy everything immediately.

## Interactions, not additive improvements

The following screen uses four selected difficult development seeds,
2000, 2003, 2009 and 2013, in both seats. It is a diagnostic panel, not a random
sample of the competitive field.

| Policy | Seyam wins / 8 | COK wins / 8 | Mean COK cash gap |
|---|---:|---:|---:|
| Crop-financed opening | 6 | 0 | −29,958 |
| Flexible capacity, annual watering and priced manure | 8 | 2 | −3,879 |
| Opening plus feed deadlines alone | 7 | 0 | −29,636 |
| Combined capacity and feed deadlines | 8 | 6 | +2,524 |

The feeding correction earns its place in combination with a farm that has
valuable assets to service. It does not independently rescue the weaker
opening. [Interaction manifests](results/phase3-interactions.json.gz) and
[funding/deadline manifests](results/phase3-funding.json.gz) preserve exact
sources, opponents, configurations and scenarios.

Earlier herd expansion displaced productive crop cohorts. More land, more
workers and larger crop limits did not reliably pay. A more detailed crop
calendar, scenario-based animal pricing, grown-feed valuation, absolute-profit
ranking and one-day inventory retention also failed to improve the chosen
combination. These candidates remain reproducible experiments, outside the
deployed module. [Development evidence index](results/phase3-development.json).

## Broader development confirmation

The frozen combined policy `59b46457…` played all four opponents on the same
16 known seeds, 2000–2015, both seats. The comparison uses exact `0098` records
from those scenarios.

| Opponent | Previous champion wins / 32 | Combined policy wins / 32 | Combined mean cash gap |
|---|---:|---:|---:|
| lonespear | 30 | 32 | +45,963 |
| GzmCR | 27 | 32 | +46,423 |
| Seyam | 9 | 28 | +20,034 |
| COK | 2 | 14 | −2,710 |

The equal-weight score is 82.8125%, up 29.6875 percentage points
[paired-seed 95% interval: 20.3125–39.84375]. Challenge score is 65.625%,
up 48.4375 points [34.375–62.5]. These intervals describe the selected known
panel; they do not remove tuning bias or uncertainty about opponent coverage.
COK remains the weakest matchup. [Full comparison](results/phase3-deadline-field-summary.json).

## Exact release candidate

The source was consolidated without changing 14,380 actions on ten saved
replays, tested as assembled observations and official external views.
[Cleanup parity](results/phase3-release-parity.json) records raw and normalized
hashes separately. Cleanup removed overwritten forecast calculations and
constant experimental branches; it did not introduce a new planner.

Independent review then found that 13 simultaneous terminal deliveries could
produce more than ten sale orders. The final policy coalesces repeated sales
only on the last action when the order list exceeds its limit. Interpreter
tests verify liquidation and explicitly demonstrate that simultaneous opponent
sales can change cash allocation. This is a real behavior correction, not an
assertion of general equivalence.

The frozen validation artifact is
[`submissions/20260909-v8/main.py`](../submissions/20260909-v8/main.py), SHA-256
`64fe323936dc9494add413eb956b0294658a88efe28572332c94676c68a09325`.
Its clean-directory packaging check compares 2,876 trajectory actions and 60
sampled actions in two isolated processes. Windows isolated peak RSS is
24,801,280 bytes. [Packaging evidence](results/phase3-packaging-final.json).

## Confirmation protocol

[The preregistration](phase3-confirmation-protocol.json) freezes identities,
effective configuration, opponent weights, seeds and practical gates before
fresh games. Validation uses 3000–3063, both seats, four opponents, both policies:
1,024 games. The reserved paired holdout uses 20000–20127 only after validation
qualification. No candidate changes or selection from partial results are allowed.

Confidence intervals resample complete seeds, retaining seats, opponents and
policies together. The environment shares randomness between weed spawning and
shop selection; changed farm occupancy can change future shops. Paired seeds
therefore compare complete policy interventions, not fixed demand paths.

Seyam and COK share a public route lineage. They remain separately reported
opponents, not two additional independent strategy families. Local strength
does not establish a live rating. Authenticated Kaggle access is unavailable;
no submission or legal-terms acceptance has occurred.

## Fresh validation: large gain, COK floor failed

Both policies completed all 512 games on seeds 3000–3063, both seats. V8 wins
128/128 against each anchor, 117/128 against Seyam and 41/128 against COK.
Its equal-four score is 80.859375%, versus 52.9296875% for `0098`: a paired
gain of 27.9296875 points [95% CI: 23.828125–32.03125]. Challenge score rises
from 10.9375% to 61.71875% [candidate CI: 55.078125–67.96875%].

All statistical/runtime gates pass except COK's 40% score floor: actual score
is 32.03125%, mean gap −4,528.29 and 10th-percentile gap −13,557.5. V8 records
zero candidate errors and a maximum decision of 113.925 ms. This is strong
improvement across the declared pool, but it does not pass its complete
promotion protocol. No holdout was opened and no live claim is made.

[Complete validation summary](results/phase3-validation-summary.json) ·
[matchup figure](figures/phase3-validation-matchups.png) ·
[realized behavior](figures/phase3-validation-behavior.png).

Further research uses these now-known seeds to diagnose COK losses. The next
[protocol](phase4-protocol.md) explicitly changes the incumbent to v8 and
reserves new validation seeds. It does not retroactively pass v8's failed gate.
