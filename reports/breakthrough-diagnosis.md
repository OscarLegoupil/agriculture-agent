# Plateau diagnosis and structural production screen

The first structural production package is rejected. It establishes an earlier,
larger herd and substantially more wheat, but delays the valuable strawberry
cohort. More productive worker actions do not compensate for the displaced
receipts. This result rejects the combined implementation; it does not isolate
the value of an earlier herd, a particular species mix, or coherent daily routes.

## Frozen incumbent and evidence limits

V8 remains the experimental incumbent, with source revision
`4b0fdc79482c42c42e9725f48318ed2184d5a6db` and executable SHA-256
`64fe323936dc9494add413eb956b0294658a88efe28572332c94676c68a09325`.
The deployed source, `submissions/20260909-v8/main.py`, and compressed source
snapshot match. The previous 512-game panel scored 128/128 against lonespear,
128/128 against Gzm, 117/128 against Seyam, and 41/128 against COK. Its 80.859%
equal-four score is supported, but its COK result failed the predeclared 40%
floor. V7 remains the historical release rollback.

The previous experiments explored many caps, priorities, feed ratios, price
thresholds and isolated resource reservations. They largely retained the same
opening, forced crop cohorts, independent investment admission and per-turn
destination assignment. In two diagnosed losses, compressing paths without
changing task order recovers only 94 and 98 movement actions, compared with
COK's 848 and 574 movement advantage. Which tasks workers combine and when they
visit them remains a larger unexplored question than shortest-path repair.

The larger negative panels are useful: extra acreage without extra productive
commissioning, depot reserves, joint single-target feed assignments and larger
input batches failed to improve the matched two-opponent score on 32 seeds.
Higher wheat production improved COK but regressed against Seyam. Those results
are stronger than the repeated four-seed screens. They do not establish that
multi-task service routes or a fully executable wheat/berry farm are unprofitable;
several candidates never established their intended production before midseason.

COK and Seyam execute coherent season-long routes with observation-based
corrections and share public route ancestry. They are useful difficult opponents,
but do not represent two independent planning paradigms. Their local strength
does not establish current leaderboard standing. No live evidence is used here.

## Fixed new development panel

The structural screen uses seeds **5000–5007**, both seats, frozen COK and Seyam,
and four policy hashes: 128 games, 32 per policy. These seeds were unused in the
archived manifest registry before this screen. They are now development data.
Validation 4000–4063 and holdout 20000–20127 remain reserved.

| Policy | Executable SHA-256 |
|---|---|
| Incumbent | `64fe323936dc9494add413eb956b0294658a88efe28572332c94676c68a09325` |
| Wool calendar | `f0ffddf56298e5eb018e6c23de91bd5148168c04cb39db45db706263990c2e33` |
| Dairy calendar | `7295ea710078e2a0873b20cc41222462ddab2d798bbeb936b6b57d9a10459a34` |
| Balanced calendar | `25c53727f3c63c9e72b4154482fc3b593e7c236cd26aa25d6a7ea47db582f546` |

These are three compositions of one combined calendar hypothesis, not three
independent strategic hypotheses. Each changes early animal targets and ranking,
animal co-product valuation, wheat and berry targets, the land ceiling, and
minimum commissioning labor. Worker dispatch remains the incumbent controller.

| Policy | COK wins / 16 | COK mean cash gap | Seyam wins / 16 | Seyam mean cash gap | Equal score |
|---|---:|---:|---:|---:|---:|
| Incumbent | 6 | −4,601.56 | 16 | +21,277.19 | 68.75% |
| Wool | 2 | −25,152.19 | 6 | −8,236.75 | 25.00% |
| Dairy | 0 | −25,078.94 | 8 | −345.19 | 25.00% |
| Balanced | 2 | −25,830.69 | 8 | +597.06 | 31.25% |

There are no draws. The paired equal-pool score changes are −43.75 percentage
points for wool and dairy, each with seed-bootstrap 95% interval
[−62.50, −25.00], and −37.50 points for balanced [−62.50, −18.75]. The intervals
resample all eight seed blocks, retaining both seats, opponents and policies.
They describe this small development panel and do not correct for candidate
selection or limited opponent coverage.

## The intended behavior changed, but the second crop cohort collapsed

All three calendars successfully reach their declared mature herd by day 15.
The missing crop production is therefore more informative than simply observing
that their target constants differ. Means below are against COK, over 16 games.

| Policy | Day-8 cows / sheep | Day-8 wheat / berries | Day-15 cows / sheep | Day-15 wheat / berries | Extra plots bought |
|---|---:|---:|---:|---:|---:|
| Incumbent | 2 / 2 | 4.94 / 23.06 | 9 / 5.44 | 6.88 / 42.62 | 2.00 |
| Wool | 3 / 6 | 13.25 / 2.38 | 6 / 12 | 22.25 / 20.50 | 2.00 |
| Dairy | 6.12 / 3 | 14.00 / 4.88 | 12 / 6 | 24.00 / 21.81 | 2.00 |
| Balanced | 4 / 5 | 13.12 / 3.50 | 8 / 10 | 23.38 / 23.00 | 2.12 |

Permitting four total plots did not make a four-plot farm appear. Wool and dairy
still buy two extra plots in every game. Balanced buys the third in only two of
the 16 COK games. The experiment cannot establish the profitability of a timely,
fully productive fourth plot.

The seed-5000, seat-0 COK replays locate the opening divergence. The first
recorded investment already differs: v8 buys a cow, while the wool calendar buys
a sheep. The new deficit ranking applies before day three; its tuple tie changes
the species order even though both farms reach two cows and two sheep by day
three. This is an opening-order confound, not proof of a material loss by itself.

The next divergence has a clear capital consequence. V8 hires six hands on days
three and five; wool hires eight. V8 owns its second plot by the start of day
five; wool remains on one plot until day six. Wool has allocated to its early
herd before that expansion and still has no strawberry seed at the start of day
six. The subsequently missing berry cohort is visible across the complete panel
by day eight. This points to startup capital and crop timing, rather than only
late care or terminal liquidation, as the earliest major failure of the package.

The reporter verifies all 128 retained replays and measures actual peak
simultaneous hands. Across both opponent pools, every structural variant employs
eight hands on days three and five, versus six for v8. Day-eight means rise from
approximately 10.1–10.2 to 11.0–11.8; all reach twelve by day fifteen. Daily reset
snapshots alone would show zero hands and cannot support this comparison.

## Added work does not recover displaced income

Against COK, seasonal strawberry receipts fall from **34,080.50** for v8 to
15,843.06 for wool, 20,298.75 for dairy and 17,354.19 for balanced. Wheat expense,
including seeds, falls from 10,580.56 to approximately 5,324–5,615. Wool adds
6,169.12 in wool receipts but loses 3,843.75 in milk receipts. Even this favorable
wool-production comparison cannot offset its 18,237.44 berry-income deficit.
These are realized accounting differences, not additive causal estimates:
supplies, opponent decisions, market prices and subsequent shop paths also change.

Successful productive actions against COK rise from 2,338.75 for v8 to roughly
2,502–2,512, while movement rises from 4,174.19 to 4,335–4,362. Labor expense rises
from 8,041.06 to 8,461–8,545. The calendars perform more work on an economy with
worse competitive returns. A worker-action count alone cannot select an economy.

All 128 games finish normally, with no candidate stderr. The largest recorded
decision is 113.418 ms. There are nevertheless physical losses: v8 has ten water
deaths across its 32 games, versus 22, 35 and 36 for wool, dairy and balanced.
Nonterminal escapes are respectively eight, three, ten and three. The wool
package thus loses badly even while reducing escapes, whereas dairy additionally
harms crop survival. Terminal escapes are retained separately and are not assumed
to be deliberate or optimal. These observations reject a single universal
"missed feeding explains everything" diagnosis.

## Smallest informative ablation

Test the earlier directed herd **with the incumbent crop calendar and original
animal purchase ordering through day two**. Retain incumbent labor and land
rules to isolate the post-startup investment change. If this still harms the
berry cohort, constrain animal admission by a funded second-crop cash runway
instead of increasing every investment priority. Only after that test should
the larger wheat rotation be combined with a successful early herd calendar.

Separately, a service-route candidate should prove that it changes task ordering
and completes useful feed/care/collection chains. Raising pickup quantities or
reserving one feed target per worker is not such a test. The route's economic
benefit must survive full-season play with the opponent reacting normally.

## Reproduction and reporting contracts

The screen manifest is `data/raw/breakthrough-season-screen.json`. Regenerate
the report without running games:

```powershell
python scripts/breakthrough_report.py --input data/raw/breakthrough-season-screen.json --replay-workers --output data/interim/breakthrough-season-summary.json
ruff check scripts/breakthrough_report.py
```

The generator also accepts compressed archives and several `--input` paths
sharing the exact champion. It rejects partial or duplicate scenario coverage,
resolved-seed mismatches, changed candidate/snapshot/opponent hashes, differing
effective configurations or dependency/environment provenance, and non-finite
cash on a DONE outcome. Conflicting overlapping attempts are rejected rather
than selected. Its six corruption probes reject missing rows, duplicate rows,
wrong seeds, changed configurations, missing DONE cash and changed opponent pins.

Outputs retain per-opponent score and paired uncertainty, mean/median/lower-tail
cash gaps, realized ledger and action means, losses, stderr diagnostics and
runtime distributions. The latter summarize per-episode action maxima and p99
values; they are not distributions of all raw action times. Milestone worker
counts are null when no verified replay is available. Replay paths and hashes
are retained when those measurements are requested.

Changing farm occupancy also changes the interpreter's weed RNG consumption and
later shop draws. Matched scenarios are full-policy interventions; the reporter
does not claim fixed-demand causal isolation. Frozen validation and holdout are
still required before promotion, as is evidence against stronger independent
opponents. No fresh-validation, hosted-runtime or leaderboard claim follows from
this rejected development package.
