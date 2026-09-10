# Actionable frontier differences after frozen validation

This diagnosis uses the preserved `0098d9e4...ffc4b` challenger and existing
seed-2000 validation replays, plus the pinned COK/Seyam public source. No new
games were run. Validation is now known diagnostic data; subsequent selection
requires a new untouched validation split. Reference code was not copied.

The largest unresolved opening difference occurs before day 1. COK buys seven
wheat seeds with its initial melon cohort; Seyam buys six then five wheat
seeds on the first two turns. The challenger instead buys four cows, a sheep
and a goose during its first six turns, while initially buying four melon
seeds. In both examined validation replays the challenger still has zero wheat
on days 1, 3 and 5. COK has 7/7/3 wheat tiles; Seyam has 10/11/7. The later
production deficit begins with the initial investment sequence, not merely
insufficient final acreage.

The first opening counterfactual should therefore reserve seed and servicing
capital for a small early wheat cohort before the fourth cow and first goose.
Its valuation must use the first executable harvest and sale, not ultimate
maximum yield. Keep later decisions adaptive; a new fixed whole-season tape is
not necessary to test this intervention. The startup-cohort experiment
can establish whether the predicted working-capital benefit survives actual
worker execution and opponent response.

## Three immediately testable execution interventions

### 1. Apply fertilizer only when it changes a reachable harvest

Against COK on seed 2000, the challenger fertilizes 102 one-shot crop tile-days;
99 occur after that day's WATER. It buys 37 fertilizer units. COK fertilizes
zero one-shot tile-days and buys zero fertilizer. Against Seyam, the challenger
has 89 fertilized one-shot tile-days, 86 after WATER, and buys 29 fertilizer;
Seyam fertilizes 39 such tile-days, 17 after WATER, and also buys none.

These are recorded action sequences located using the preceding observation's
actor position and tile. Pickup, DROP, PLACE and fertilizer-order counts below
likewise describe requested operations and the observed stock they address;
they are not a success-validated transaction ledger. An after-WATER application is not automatically
worthless: it can still support a later watering while fertilizer remains
active. The economic test must consider that later opportunity rather than
count every reversed pair as lost revenue.

Official `_apply_unit_action` probes establish the consequential distinction:

| Probe | Result |
|---|---|
| Wheat age 2: WATER then FERTILIZE | 2 held wheat; one fertilizer spent |
| Same tile: FERTILIZE then WATER | 3 held wheat; one fertilizer spent |
| Wheat already at its six-unit cap: FERTILIZE then WATER | Still six wheat; fertilizer spent |
| Strawberry age 9, either action order, then official daily refresh | Two strawberries in both cases |

One-shot WATER grows immediately; ongoing production occurs at daily refresh.
The current task generator admits FERTILIZE without checking `watered_today`
or remaining held-product room. Its urgent WATER value can win the assignment
before fertilizer acquisition. Increasing fertilizer priority alone would
introduce missed-water risk when the input is unavailable.

**Smallest useful change:** calculate remaining incremental units before the
intended harvest. Admit one-shot fertilizer only if a reachable future WATER
can add yield below the cap and that extra yield repays fertilizer plus work.
When the required input is already carried and watering is safe to defer one
turn, schedule fertilizer first; otherwise water to preserve the crop. Compare
this with the simpler recurring-only fertilizer restriction. Keep recurring
fertilizer eligible after watering because its growth transition is different.
Measure fertilizer purchases, applications at cap, incremental sold crop units,
water losses and match score. Do not claim the application cost is saved income
without re-running the complete official game.

### 2. Preserve useful inputs during product delivery

The challenger uses whole-inventory DROP for production deliveries. In the
seed-2000 COK matchup these drops return **143 wheat and 78 fertilizer** to
the shed. COK returns only **22 wheat and zero fertilizer** through DROP;
it additionally uses 33 premium-product PLACE operations and four fertilizer
PLACE operations. This changes whether workers must reacquire inputs after
delivering milk, wool or crops.

An official action probe starts a worker at shed access carrying six wheat,
three milk and four fertilizer. `PLACE MILK 3` deposits the milk and preserves
all ten input units. `DROP` deposits everything and clears the inventory.
Both actions take one worker turn. Selective PLACE obeys the same shed room
limit and is available from the same shed-access positions.

**Smallest useful change:** at a planned delivery, use selective PLACE for a
single valuable sale product if the worker holds inputs for admitted nearby
tasks. Use DROP when retained inputs have no remaining purpose or disposing of
several products is worth the extra reacquisition. Update shared storage
reservations for the deposited quantity, and project same-turn final sales
from that exact quantity. Preserve explicit full liquidation on the final
day. This targeted intervention is distinct from the previously rejected
wholesale nightly-delivery strategy.

### 3. Batch inputs by an executable local service circuit

COK's seed-2000 workers pick up six wheat 97 times and commonly collect eight
fertilizer. The challenger picks up three wheat 126 times and mostly four
fertilizer. The official pickup implementation permits a worker to take six
wheat and eight fertilizer: an interpreter probe confirms all 14 units remain
carried. There is no three-wheat/four-fertilizer worker limit; these are policy
choices. The common shed's 100-unit cap still applies to inventory transfers
and nightly delivery.

**Smallest useful change:** for a worker about to acquire feed, count nearby
animals it can reach and feed before reset, capped initially at six. Reserve
that quantity from shared stock. For fertilizer, count only admitted,
value-positive local applications, initially capped at eight. Update both
pickup quantity and the number of workers allowed to fetch the same resource;
changing only the quantity while retaining `ceil(demand/3)` can oversupply
couriers. Test with selective delivery so a larger input batch is not dumped
immediately on the next product sale.

This is a COK-derived hypothesis, not a universal rule: Seyam uses many
two-wheat pickups in the examined match and remains stronger than the
challenger. Batch size must earn its place through less travel and more
serviced tasks, with no increased shortages or idle input stock.

## Fertilizer reserves and opening valuation

The market forecast does **not** directly choose to hold fertilizer. Its
fertilizer scenario adds expected animal supply with no town demand, so it
projects non-increasing fertilizer prices. The policy's actual reserve is a
separate rule: up to 12 units from planted-tile count while cash is at least
1,000. That count does not distinguish an immature strawberry from a crop
with an imminent profitable growth event. The model's crop price forecasts
and the reserve rule should not be conflated in an ablation.

Across all 128 challenger games against COK, fertilizer purchases average
44.63 units costing 2,153.52 coins, while sales average 250.68 units. Against
Seyam the corresponding purchase values are 47.63 units and 2,730.80 coins.
Buying and selling in different periods is not inherently a defect; the
question is whether input timing and marginal applications justify it.

The most informative reserve replacement is the number of profitable
applications that can execute before the next automatic input delivery,
minus carried fertilizer, with a startup cash reserve for committed seeds,
feed and hires. This requires the actual application-admission logic above;
using every planted tile as a proxy retains the same economic mismatch.

Do not credit future crop growth as current working capital. A starter cohort
can be excellent at season-end yet fail before its first harvest if seed,
animal, feed and hiring commitments exhaust cash. The new opening experiment
should therefore record the earliest harvestable wheat cohort, actual seed
placement, initial worker capacity, and the first investment delayed by cash.

## Evidence and reproduction

Source pins and environment hashes remain those in
[`phase2-frontier.md`](phase2-frontier.md). The selected full replays are the
`0098...-reference-{cok,seyam}-main-2000-0.json` files under ignored
`reports/replays/phase2-validation/`, identified in the committed validation
manifests. The records concern the exact evaluated challenger, not an edited
development source.

The read-only extraction is maintained in
[`scripts/phase3_frontier_measures.py`](../scripts/phase3_frontier_measures.py).
It records replay hashes and writes the compact committed
[`phase3-frontier-measures.json`](results/phase3-frontier-measures.json).
Fertilizer timing and cap contracts are covered by the existing interpreter
tests. Selective delivery and larger input pickups are checked separately by
[`scripts/phase3_frontier_probes.py`](../scripts/phase3_frontier_probes.py), with
environment provenance and results in
[`phase3-frontier-probes.json`](results/phase3-frontier-probes.json).

```sh
python scripts/phase3_frontier_measures.py --replays reports/replays/phase2-validation
python scripts/phase3_frontier_probes.py
python -m pytest tests/test_phase3_contracts.py -q
```

Both scripts accept `--output PATH` and write UTF-8 JSON. They do not run games.
The extraction requires the saved replays; if absent, restore the exact source
snapshot `0098d9e4f77e2420cb4a09abd47e49f5160009cd0818ae37a793bc3e419ffc4b`
from `reports/sources/` and regenerate the documented seed-2000, both-seat
games with `scripts/benchmark.py --candidate PATH --opponents
data/raw/reference-cok/main.py data/raw/reference-seyam/main.py --seeds 2000
--output data/raw/frontier-reproduction.json --replays
reports/replays/phase2-validation` under the pinned environment. Fetch the
reviewed opponents using `scripts/fetch_challenge_references.py` first.

These probes isolate action contracts and make no full-match performance
claim. They do not expose future state to a deployed agent.
