# Market forecast contracts: two corrections, no new games

The incumbent's **uniform with-replacement shop distribution is correct**.
The official interpreter draws from the entire sorted catalog every third
end-of-day transition, including types already present, until eight instances
exist. Multiple copies consume independently. A single-product shop consumes
two units per activation; other shops consume one of each listed product. Six
activations per default day therefore give the existing 12/6 demand constants.
The town center consumes one of every primary product per day, excluding manure.
There is no market-inventory decay or nonnegative inventory floor.

Two executable discrepancies remain:

1. **Interval timing.** Define a trace point as inventory at observation-day
   `future`, with sales projected into that point as in the incumbent. A shop
   unlocked at the transition into day three has not consumed anything before
   that boundary; its first consumption is step 72, after unlock. The existing
   `future // 3 - day // 3` demand term charges its first full day too early.
   It also charges a full day of town demand when the current observation is
   already partway through that day. The isolated correction counts remaining
   activation steps and uses shops present during the interval ending at each
   trace boundary. Future instances remain uniform expected demand, not a draw
   from future realized state.
2. **Supply at the dollar floor.** Official SELL always transfers cash and
   removes the held item, but increases market inventory only when the sale's
   unit quote exceeds one. The incumbent adds all projected sales, allowing
   fictitious oversupply to delay recovery indefinitely. The correction applies
   the same unitwise inventory admission rule to each projected sale batch.
   Market inventory remains free to become negative through consumption or
   purchases; adding an inventory floor would be a new error.

Ten interpreter-backed tests cover current full and partial intervals, duplicate
shops, actual end-of-day unlock timing/catalog/cap, and 1,000 sequential unit
sales each for wool, milk, berries and manure. The supply helper matches official
integer-sale inventory exactly. Fractional expected quantities and placing daily
sales before daily consumption remain model approximations; real trades and
consumption interleave throughout the day. These corrections do **not** validate
the inherited production, travel, care or future-feed assumptions.

## Isolated models and observed forecast sensitivity

`scripts/phase4_forecast_contract.py` builds three variants of exact v8:

| Variant | Frozen SHA-256 |
| --- | --- |
| `town_timing` | `92ef21947645d5d3d15879e6d7874ed17838c2d8c03ebce4b22f87126457b6a8` |
| `sale_floor` | `000e646a6b8d8a1d2061ea6b8e7c1d3494c4853b217610ade73759abd6ed80c9` |
| `both` | `1e43a5d7673adff3d44790da79b06323be0fd95be89c1222407e37b25eeb3bf2` |

Only town demand and/or sale-batch inventory accumulation changes. Investment
ranking, price curve, output projection and blended seven-day sale windows stay
fixed. All helpers use public observations and verified default configuration;
they do not read the environment seed or future shops. This is an expected
market path, not a surrogate game simulator or a newly validated scenario league.

On 32 known observations from four saved COK losses, timing correction changes
the largest investment quote by **17.86 cash/unit**: milk at step 328 of seed
3063 becomes 123.57 rather than 141.43. Floor correction changes the largest
quote by **70.50**: berries at step 480 of seed 3029 seat zero become 162.00
rather than 91.50. This late change alone does not imply an investment gain;
the policy's remaining crop opportunities may already be closed. The maximum
isolated forecasting runtime was 0.491 ms for timing and 1.436 ms for the combined
model, measured once per observation. These are local diagnostic samples, not
full-agent or hosted latency distributions.

Exact per-observation quotes, source hashes and timings are saved in
`reports/results/phase4-forecast-contract.json`; source snapshots are under
`reports/sources`. These diagnostic probes ran no games. The subsequent frozen
screen below tests the floor correction and timing added to it. Verify
whether changed quotes alter an actual funded investment before interpreting
score differences as improved economic modeling.

Run the executable contracts with
`python -m pytest tests/eval/test_phase4_forecast_contract.py -q`.

## Frozen screening protocol

Authorize exactly **32 known-development games**: `sale_floor` and `both`, each
against pinned Seyam and COK on seeds 3000, 3017, 3042 and 3063 in both seats.
This compares the floor rule against v8 and isolates timing correction added to
that rule. It does not test timing alone. Candidate bytes above remain frozen.
Use `python scripts/phase4_forecast_contract.py --screen --workers 4`; without
`--screen` the command only checks and prints identities. The runner refuses
to overwrite evidence and waits for the existing production-interaction panel
to be complete before claiming four workers. No automatic extension follows
the 32-game budget, and no new validation or holdout is used.

## Completed screen: contracts corrected, competitive gain absent

All 32 games completed normally. Both candidates preserve every original
win/loss outcome: **8/8 Seyam and 4/8 COK**, or 75% equal challenge score.
Their paired score differences are zero on each of the four seed clusters;
the resulting bootstrap interval [0, 0] records this observed invariance and
does not establish true equivalence on unseen seeds. Reject both for promotion:
they provide no practical score improvement and worsen mean COK cash gaps.

| Policy | Mean Seyam cash gap | Mean COK cash gap | COK median gap | COK tenth-percentile gap | Maximum action time |
| --- | ---: | ---: | ---: | ---: | ---: |
| V8 | +7,646 | −1,745 | −2,567 | −10,538 | — |
| Floor correction | +7,105 | −3,112 | −3,918 | −10,538 | 336.802 ms |
| Floor + timing | +7,617 | −3,188 | −3,981 | −10,007 | 233.967 ms |

The seed response shows why an apparently correct rule is not enough to select
a stronger model. Mean COK gaps across the two seats are:

| Seed | V8 | Floor | Floor + timing |
| --- | ---: | ---: | ---: |
| 3000 | +3,984.5 | +1,132.0 | +596.5 |
| 3017 | −10,538.0 | −10,538.0 | −8,426.0 |
| 3042 | +7,455.5 | +5,163.5 | +5,083.0 |
| 3063 | −7,881.0 | −8,205.0 | −10,007.0 |

Adding timing to the floor treatment changes mean COK gap by −76.5 and Seyam
gap by +512.5, without converting an outcome. Neither this four-seed screen
nor the quote probes validate the daily approximation as a complete economic
rollout. In particular, unit-sale admission is exact for the tested batches,
but the model still batches supply before demand, approximates future output,
and ignores actual future route execution. Calendar and inventory accounting
improvements can change a biased forecast without improving its investment
ranking. Keep these tests and negative results, not an unsupported model upgrade.

Candidate errors, opponent errors, reported failed work and stderr turns are
all zero. Full-agent runtime remains below the local 500 ms ceiling on this
panel; this is distinct from the much smaller standalone helper timings above.
All comparisons use the same opponent hashes, configuration, resolved seeds
and source snapshots. The complete manifest is archived at
`reports/results/phase4-forecast.json.gz`; matched comparisons against v8 and
between candidates, including both-seat seed responses, are saved in
`reports/results/phase4-forecast-summary.json`. The 32-game budget is complete;
no additional games or fresh data are justified by this result alone.
