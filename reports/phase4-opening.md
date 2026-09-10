# Opening cash allocation and first-cohort care

The first consequential difference in COK loss 3029 is **not the initial farm
size**. Both agents finish day zero with seven wheat, twelve melon, two cows
and two sheep. They subsequently allocate the same limited early capital and
worker actions differently. This diagnosis uses both saved seats, their verified
cash ledgers and official successful-action reconstruction; it runs no games.
The detailed table below uses v8 in seat zero. Days are zero-indexed.

| End of day | V8 cash | COK cash | V8 cow/sheep/goose | COK cow/sheep/goose | V8 berries | COK berries |
| --- | ---: | ---: | --- | --- | ---: | ---: |
| 0 | 39 | 24 | 2/2/0 | 2/2/0 | 0 | 0 |
| 3 | 1,099 | 27 | 2/2/0 | 3/2/0 | 0 | 0 |
| 5 | 261 | 303 | 2/2/0 | 4/2/0 | 5 | 4 |
| 6 | 1,324 | 1,414 | 2/2/0 | 4/2/0 | 12 | 4 |
| 7 | 530 | 400 | 2/2/0 | 6/3/0 | 22 | 8 |
| 8 | 289 | 2,034 | 3/2/2 | 6/4/0 | 25 | 11 |
| 9 | 232 | 2,831 | 3/3/2 | 6/6/0 | 26 | 11 |
| 10 | 11,665 | 16,031 | 3/6/2 | 6/6/0 | 33 | 11 |

Across days 0–9, v8 spends 3,300 on animals and 2,900 on berry seeds;
COK spends 5,400 and 1,100 respectively. V8's total seed spending is 4,360
versus 2,710. Labor costs are **507 versus 719**: blanket claims of excessive
early hiring are unsupported here. Purchased wheat costs are 764 versus 1,884;
COK funds a larger animal workload. V8 spends 3,000 on land versus 1,000,
recorded for accounting completeness; land-specific interventions are outside
this diagnosis.

Realized income through day nine is 9,163 versus 11,544. Wool contributes
2,723 versus 4,393, manure 3,087 versus 3,859, milk 2,468 versus 2,494, and
wheat 885 versus 798. None of the new berries has produced yet. These receipts
explain a working-capital timing difference, not proof that berries are globally
unprofitable. The large day-ten melon receipt is comparable: 12,808 versus
13,152. V8's second initial cow harvest is delayed, but both farms actually
produce six milk at day ten; harvested units alone must not be called production.

## A material missed return on already-owned animals

On day zero v8 successfully cares for both cows and neither sheep. COK does
the reverse. Cows first produce on day eight and have room to accumulate their
capped first yield despite waiting a day. Sheep first produce on day six and
need earlier care to fill that first cap. V8's first sheep yields are **5 + 4**,
versus COK's **6 + 6**. The official ordering consumes the accumulated bonus
before adding care on the production transition; day-five care cannot repair
the first day-six sheep yield.

V8 then misses one sheep's feed on day eight. At the day-nine production
transition it loses three banked care units: the two sheep hold **1 + 4** versus
COK's **4 + 4**. Together these are **six missing wool units by day nine from
identical initial assets**, repeated in both seats. Current wool quotes near
200 imply roughly 1,200 gross cash of opportunity before price impact, feed
and displaced work. This is a mechanism-based estimate, not a replayed sale
gain. Earlier-care prioritization can change other tasks and future shop draws.

## Three bounded opening interventions

1. **First-cohort care slack.** Before the first production, prioritize the
   animal whose remaining service opportunities barely cover its useful care
   deficit: holding cap minus base yield minus pending care. The next EOD care
   cannot count toward a production occurring in that same transition. This
   should prefer the two sheep before cows on day zero, while preserving feed
   prerequisites and escape protection. Limit the intervention to the initial
   cohort so the experiment tests startup capital from existing assets. Verify
   first wool reaches twelve without reducing first milk, and measure changes
   in the early cash trough. This is distinct from uniformly increasing CARE
   priority or buying more animals.

2. **One funded early animal in place of the next berry batch.** After startup,
   permit one model-selected additional cow or sheep before the inherited
   day-eight admission release, paying from capital otherwise assigned to five
   berries and reserving its feed through first production. Keep total herd
   capacity unchanged and require an existing worker service plan. At the
   observed start of day five, wool is 215 and wheat 31. An ideally cared sheep
   placed then first produces on day eleven: six wool worth 1,290 at that current
   quote, versus 500 purchase plus six feed worth 186. The resulting **604**
   gross margin excludes care/travel, market impact, price uncertainty and the
   deferred berry receipts; it is a screening rationale, not a forecasted win.
   Daily manure is extra potential value, not assumed liquid cash. A cow costs
   400 but waits eight days, so choosing sheep versus cow must use observed
   economics rather than copying COK's sequence.

3. **Wheat harvest as a working-capital decision.** V8 harvests fourteen wheat
   units on day two from the seven initial plants; COK waits until day four
   and takes twenty-eight. Early receipts can be valuable, but consuming those
   plants requires reseeding and repeated sow/harvest work. Test a rule that
   preserves annual wheat growth while currently held cash and inputs cover
   funded obligations, allowing early harvest only to prevent an actual
   shortfall. This is a cash-feasibility intervention, not an unconditional
   delayed harvest. Compare initial wheat yield, reseed expense, actual care
   completion and the minimum cash balance before melon sales. It may hurt
   startup liquidity and should be rejected if that happens.

Each hypothesis earns at most one initial **16-game known-data screen** against
Seyam and COK on seeds 3000, 3017, 3042 and 3063, both seats, if implemented.
Run the first-cohort care mechanism first; do not combine all three before
knowing which produces its predicted intermediate behavior. No screen is run
by this report, and no fresh validation or holdout is touched. The sample loss
is deliberately diagnostic, so it cannot select an opening by itself.

Reproduce the compact first-ten-day ledger and actual initial-cohort service
counts with `python scripts/phase4_opening.py`. The saved evidence is
`reports/results/phase4-opening-audit.json.gz`; original replay hashes and the
verified ledger hash are included. The script requires the previously generated
local loss ledgers and large saved replays, neither of which is a deployed
policy input. Public COK behavior is an independently attributed diagnostic
reference, not a source of copied routes or layout code.

## Frozen screen candidates

Two isolated builders are now available through `phase4_opening.build(name)`;
neither changes the deployed source or has been benchmarked yet:

- `care_slack`: `adce3c00296b534851a9892ad821904e073e9b6b4d17ab23010815d3c25876e2`.
  Replace the fixed 60 CARE priority with 60 times remaining useful care deficit
  divided by remaining care-effective days. The first-cycle target is capped
  at the holding limit minus one; later cycles cannot accumulate more useful
  care than their interval. Care on a production transition targets the next
  event, resetting the pending amount consumed by the imminent event. No value
  is assigned to bonuses that cannot appear by day 29. This assumes existing
  harvest tasks clear previously held output, and does not prove route feasibility.
- `early_herd`: `b343911959b3204ee44f131ee0aa39192ff68698c45ddf8f577dff2b6cda127e`.
  Move the existing mixed opening admission restriction from day eight to day
  four. This deliberately tests the existing model's unrestricted funded ramp,
  rather than the more constrained single-animal hypothesis above. All cash
  guards, shared 18-animal capacity, production ranking and crop policy remain
  unchanged. Observe realized purchases before claiming the intended change.

Frozen source bytes are in `reports/sources/<hash>.py.gz` and local executables
under `data/interim/phase4-opening/<name>/<hash>/main.py`. Three interpreter-backed
tests verify that the care ranking selects the two sheep first in a two-cow,
two-sheep witness, permits both species to attain their first cap when subsequent
service is available, preserves next-cycle care on a production transition, and
excludes unsaleable terminal bonuses. The witness is a calendar contract, not
proof the full scheduler will execute that sequence. The following fixed screen
was run after these candidate identities and tests were frozen.

The authorized screen budget is **32 games total**, exactly these two frozen
candidates against the same two challenge references on seeds 3000, 3017,
3042 and 3063 in both seats. No automatic extension is permitted. Run
`python scripts/phase4_opening.py --screen --workers 4`; the default invocation
continues to perform diagnosis only. The screen refuses to overwrite prior
results or start before `phase4-joint-field.json` is complete, preserving the
eight-worker concurrent resource limit. Candidate identities are checked before
execution and again before the complete flag is written. The early-herd source
was independently checked to differ from v8 by exactly the single admission-day
replacement.

## Completed screen: reject both candidates

All 32 authorized games completed. The exact matched incumbent panel contains
16 v8 games, reused for each challenger; no new validation seeds were inspected.

| Policy | Seyam wins | Mean Seyam gap | COK wins | Mean COK gap | Equal challenge score |
| --- | ---: | ---: | ---: | ---: | ---: |
| V8 | 8/8 | +7,646 | 4/8 | −1,745 | 75.00% |
| Care slack | 7/8 | +7,889 | 2/8 | −9,717 | 56.25% |
| Early herd | 8/8 | +5,957 | 0/8 | −19,020 | 50.00% |

Whole-seed paired bootstrap intervals for aggregate improvement are
−18.75 points [−62.5, +25.0] for care slack and −25.0 points [−50.0, 0.0] for
early herd. Four seed clusters provide little precision; these are screening
diagnostics, not persuasive generalization intervals. The practical outcome is
nevertheless clear: neither intervention earns broader selection.

| Mean against COK | V8 | Care slack | Early herd |
| --- | ---: | ---: | ---: |
| Day-seven animal count | 4.0 | 4.0 | 10.0 |
| Day-seven cash | 617 | 308 | 257 |
| Full-season wool units sold | 160.88 | 173.75 | 142.38 |
| Wool income | 18,683 | 18,602 | 21,498 |
| Milk income | 13,905 | 17,173 | 19,938 |
| Labor expense | 7,968 | 7,837 | 8,280 |
| Wheat expense, including seeds | 9,610 | 9,320 | 11,050 |
| Animal purchase expense | 7,675 | 8,438 | 7,750 |
| Berry income | 28,293 | 26,013 | 25,105 |
| Own final cash | 68,857 | 65,806 | 72,001 |
| Opponent final cash | 70,601 | 75,523 | 91,021 |

Early admission changes the intended capital path: ten animals by day seven
instead of four. It improves own livestock receipts and own mean cash, but
changes crop receipts and the opponent's realized outcome even more. Thus the
experiment directly rejects using higher own cash as evidence of competitive
improvement. Changed action paths can also alter the interpreter's future shop
randomness; the increase in opponent cash is not attributable solely to market
effects or a known response policy.

Care slack changes full-season assignments and later production mix, beyond
the initial calendar witness. More COK wool units do not produce more wool
income. The result does not falsify the six-unit opening diagnosis, but rejects
this general priority formula as its implementation. A future attempt should
measure whether the initial service actually changes before attributing results
to care timing. Do not retain either intervention in the deployed policy.

All candidate and opponent statuses are DONE; reported failed work and stderr
turns are zero. Maximum observed action time is 145.067 ms for care slack and
292.617 ms for early herd. This is within the local 500 ms ceiling, with less
headroom than the original runtime witness; concurrent benchmark load prevents
attributing that difference to the policy alone. Reliability did not rescue
their failed competitive results.

Complete records are archived in `reports/results/phase4-opening.json.gz`.
`phase4-opening-summary.json` preserves full matched source/environment/seed
checks, cash tails, per-opponent paired intervals and mean financial telemetry.
The budget is exhausted for these hypotheses; no automatic extension follows.

## Initial animal input sequence, after the rejected care formula

The care formula's failure warrants inspecting prerequisites rather than another
priority multiplier. Exact successful-action reconstruction for COK seed 3029,
v8 seat zero, shows these decision steps on day zero:

| Policy / cohort | Purchase | PLACE | FEED | CARE |
| --- | --- | --- | --- | --- |
| V8 cows | 0, 1 | 3, 6 | 7, 11 | 8, 12 |
| V8 sheep | 4, 7 | 14, 19 | 23 for one sheep | none |
| COK cows | both at 0 | 4, 12 | none | none |
| COK sheep | both at 0 | 4, 5 | 7, 11 | 8, 12 |

The remaining v8 sheep is not fed until the following day; its first successful
sheep CARE is decision 45. Original full-ledger checks verify actual animal
purchases, while copied official unit actions recover successful FEED at step
23 even though the following observation has already reset daily flags. The
compact event record is `reports/results/phase4-opening-sequence.json`.

V8's two-animal in-flight cap postpones sheep orders until cows are placed.
Cow-first inventory enumeration claims nearby sites first; when sheep arrive,
intervening crop allocations put them at `(4,1)` and `(4,0)`, farther from the
depot than COK's first sheep. Raising a CARE score cannot repair a missed
opportunity when the animal has not yet arrived or feed is unavailable. COK
uses fewer initial hands, so additional initial workers are not the demonstrated
missing prerequisite.

Two small **unimplemented, unbenchmarked** sequencing interventions follow:

- Admit up to four in-flight initial animals on day zero, retaining the existing
  two-cow/two-sheep opening caps and all subsequent admission logic. This isolates
  the purchasing queue but may still let cow-first assignment move sheep tasks.
- Commission the initial sheep before cows, consistently in both purchase and
  available-animal task ordering. Retain the same four total assets, funding
  rules and later herd policy. Changing only purchases can change destinations
  when newly purchased cows enter the task pool.

Neither intervention copies routes. The causal target is earlier useful care
from the same owned assets, measured by actual PLACE/FEED/CARE times and first
wool output before examining score. Both remain hypotheses until the full
controller performs the intended sequence. No additional games are authorized
by this diagnosis.
