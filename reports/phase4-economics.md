# Economic diagnosis after v8 qualification failed

V8's 41/128 COK wins fail its declared 40% floor. The 3000–3063 validation panel
is now development data; the final holdout remains unopened. The frozen source
in this analysis is `64fe323936dc9494add413eb956b0294658a88efe28572332c94676c68a09325`.
The new evidence argues against attributing every loss to excessive dairy. Feed
economics and the timing of productive cohorts remain consequential even when
the final herd resembles COK's.

## Coverage and accounting

The saved 3000/3001 COK replays are all wins: +2,747, +5,222, +9,925 and +2,821.
Four separately recorded reproductions of 3029/3063 supply actual losses.
`scripts/phase3_field_economics.py` reconstructs both players' unit/market phases
on copied preceding observations. All **11,504 cash transitions** across these
eight replays agree with the subsequent recorded balances. No policy or random
future transition is executed by that extraction. The four reproduction games
are duplicate known scenarios, not additional independent observations.

Daily cohorts, harvest quantities, trades, prices and replay hashes are saved in
[`results/phase4-economic-ledgers.json.gz`](results/phase4-economic-ledgers.json.gz).
Opponent private inventory appears only in this offline accounting. It is not
an input to either tested candidate.

Across the full COK panel, losing games have *higher* mean own cash: 81,491 versus
78,162 in wins. Their day-15 herds average 11.80 cows/4.02 sheep/2.16 geese,
versus 6.00/8.20/3.76 in wins. This post-hoc association identifies a weakness
worth examining, but demand influences both the herd and the outcome. It does
not prove that applying a universal cow cap improves matches.

## Three economic bottlenecks

**Feed is a persistent expense gap.** Product net balances below subtract both
purchased products and seeds; gross wheat turnover is not income retained.

| COK scenario | Final v8 gap | v8 net wheat | COK net wheat | COK wheat advantage |
|---|---:|---:|---:|---:|
| 3029, seat 0 | -21,530 | -3,335 | +1,260 | +4,595 |
| 3029, seat 1 | -21,401 | -4,419 | +1,074 | +5,493 |
| 3063, either seat | -7,881 | -7,101 | +2,910 | +10,011 |

In 3063 v8 buys 225 wheat for 9,673 and spends 610 on wheat seeds, receiving
3,182 from sales. COK spends 21,458 on purchased wheat and 1,290 on seeds, but
receives 25,658 from sales. COK's larger turnover is not itself advantageous;
its grown production makes the net balance better. Its day-15 farm has roughly
38 berries/17 wheat/14 animals, compared with 43 berries/7 wheat/18 animals for
v8, on the same three quadrants. V8's extra berry net receipts of 5,211 only
partially offset the wheat gap. The same wheat deficit appears in all four
saved wins, where other products compensate for it.

This warrants an executable feed-versus-other-crop allocation comparison, not
a claim that seventeen wheat tiles is intrinsically optimal. The earlier
phase-3 feed experiment used the older controller before its annual growth and
deadline fixes; its assumed two-unit early harvest is not automatically the
right valuation for v8. Conversely, the existing feed bonus is still a heuristic,
not a measured marginal action value.

**Mature herd counts conceal missing early receipts.** In 3063 both policies
reach ten cows, but COK adds cows on days 3, 5, 7, 9 and 11. V8's new cow cohorts
arrive on days 10, 11 and 13. By the end of day 17, COK has harvested 93 milk
against v8's 36. Both harvest another 186 units thereafter, so the final 57-unit
gap is already present at that checkpoint. COK sells 279 milk for 22,176 versus
222 for 15,956. Earlier receipt timing and quantity both matter; extra late cows
are not equivalent to funding earlier cohorts.

In 3029 the day-15 v8 herd is already sheep-heavy: eleven or thirteen sheep,
with five or three cows. Yet COK's earlier six-cow cohort earns 13,226 or 20,671
more milk income, while its twelve sheep earn 18,955 or 10,374 more wool. These
losses are not explained by excessive v8 cow count. Exact care/harvest defects
need to be separated from cohort timing before attributing all missing product
to investment. Earlier funded cohorts remain a hypothesis, with the known risk
of displacing profitable berries or feed during startup.

**The forced crop route can override the prospective ranking.** At actual
3029 seat-0 step 328, the inherited new-cohort valuation assigns a final proposed
berry a value of -1.32 while wheat is +44.32 and tomato +24.26, in the model's
cash-per-tile-day units. The current-price opening rule nevertheless forces
berries until day 15. A copied-state official market probe verifies that the
alternative tomato seed costs 50 and is affordable. This checks feasibility,
not realized future profitability.

The negative number needs qualification: one berry seed is already owned, while
`crop_value` charges a new seed. A negative new-seed value is not proof that
planting an owned seed has negative marginal value. An earlier informal
calculation on 3063 also applied fertilizer when the controller's price gate
would disable it; the recorded instrumented probe corrects that assumption.
The supported finding is a conflict between the heuristic and its prospective
ranking, whose reliability still requires experimental testing.

## Bounded cohort experiment

`scripts/phase4_cohorts.py` preserves v8 through day 7, including eighteen sampled
real-observation action-parity checks. It tests two original changes:

- `economic_after_startup` removes the forced crop override from day 8 onward.
- `guarded_cohort` retains the override only when its existing forecast value
  is positive and at least as large as the existing wheat value, including the
  inherited feed bonus. This introduces no new fitted numerical threshold.

Both reject the recorded negative prospective berry choice. Two copied-state
official purchases verify the selected alternative's seed cost and availability.
The benchmark uses uninstrumented frozen artifacts, not the diagnostic code.
Each candidate receives sixteen games on known 3000, 3017, 3042 and 3063,
both seats against unchanged Seyam and COK.

| Policy | Seyam wins / 8 | Mean Seyam gap | COK wins / 8 | Mean COK gap |
|---|---:|---:|---:|---:|
| V8 | 8 | +7,646.13 | 4 | -1,744.75 |
| Economic after startup | 6 | +3,598.63 | 4 | +472.75 |
| Guarded cohort | 5 | +4,102.00 | 3 | -2,639.75 |

Neither earns promotion. Both reduce berries to roughly 23–32 by day 15, but add
later melons, carrots and tomatoes rather than exclusively expanding feed.
That broad production substitution loses Seyam matches without adding COK wins.
A positive mean COK cash gap for the first candidate is insufficient evidence
of improvement. These are full-policy interventions: farm occupancy and opponent
response can change subsequent shops on the same seed.

Artifacts:

- `economic_after_startup`:
  `483858b24beba71f0420859d00144c5e30a7e0ba9f07a5ec45f13f368cfa053e`.
- `guarded_cohort`:
  `fa9353f54164c8ef7e773ab79ffe664b638c320c2a2f1efcb8eb12742ab2e09c`.

All 32 games finish normally, with no stderr turns. Maximum action time is
103.37 ms and 71.42 ms respectively. Complete provenance, checks and per-game
results are in [`results/phase4-cohorts.json.gz`](results/phase4-cohorts.json.gz).

```sh
uv run python scripts/phase4_cohorts.py --check-only
uv run python scripts/phase4_cohorts.py --workers 4
```

The next useful economic work should isolate feed replacement and earlier
receipts from care/service quality. The negative result argues against simply
trusting the existing crop valuation more broadly, adding scenario count, or
repeating the rejected absolute-profit objective without a new mechanism.
