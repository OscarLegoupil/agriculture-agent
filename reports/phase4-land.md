# Land ownership, timing and executable expansion

The observation that strong agents use three plots is useful, but purchased plots and total ownership differ. The official environment starts with NW and sells NE, SW, SE in that order for 1,000, 2,000 and 4,000. Three purchases mean all four quadrants and 7,000 expenditure; three total quadrants mean two purchases and 3,000 expenditure.

Frozen v8 (`64fe3239...`) buys exactly **two additional plots in all 512 completed validation games**. Its policy caps total ownership at three. Those seeds are now known development data. The opponent comparison below uses sixteen saved validation trajectories, seeds 3000/3001 against four pinned references in both seats, plus four COK loss reproductions on 3029/3063. These are local public references, not a representative sample of all top live agents. Replay and executable hashes are preserved in [the measurement file](results/phase4-land-diagnosis.json.gz).

| Policy | Observed games | Additional purchases | First purchase | Second purchase | Third purchase |
|---|---:|---|---|---|---|
| v8 | 20 | 2 throughout | day 4, hour 21 | day 9-11 | never |
| COK | 8 | 2 in four; 3 in four | day 6, hour 4 | day 11, hour 0 | day 12, hour 0 in 3001/3029 |
| Seyam | 4 | 2 throughout | day 7, hour 1 | day 10, hour 20 | never |
| Gzm | 4 | 2 throughout | day 7, hour 1 | day 10, hour 1 | never |
| Lonespear | 4 | 1 throughout | day 9, hour 1 | never | never |

Days and hours are zero-based interpreter observations. Purchases are realized ownership changes, not requested orders. Pre-turn cash is not the full purchasing budget: COK buys its first plot with 458 cash in seed 3000 after a same-turn six-unit wool sale. It ends that turn with 743. A policy that only counts starting cash would miss this feasible investment. V8 nevertheless expands its first plot earlier, so simply accelerating its first land purchase does not address the observed gap.

## The meaningful difference is commissioning productive capacity

| COK matchup, seat 0 | v8 peak productive tiles | COK peak | v8 labor expense | COK labor expense | v8 SW reaches 20 productive tiles | COK SW reaches 20 |
|---|---:|---:|---:|---:|---|---|
| 3000 | 68 | 75 | 7,828 | 5,977 | day 13 hour 23 | day 12 hour 22 |
| 3001 | 68 | 87 | 8,116 | 5,977 | day 17 hour 22 | day 11 hour 21 |
| 3029 | 68 | 90 | 8,027 | 5,977 | day 12 hour 22 | day 11 hour 23 |
| 3063 | 68 | 75 | 7,972 | 5,977 | day 13 hour 21 | day 12 hour 22 |

Productive means a currently planted crop or animal, not an empty structure. Peak counts are simultaneous total footprint; they do not sum unrelated per-quadrant peaks. Labor expenditure is reconstructed from realized intraday hires using the official Fibonacci cost; no observed hour-23 hiring is included in that measure.

COK's fourth plot is partially filled rather than automatically saturated. In 3001, it has ten productive SE cells by day 13 and sixteen by day 20 (maximum eighteen). In 3029 it has seven by day 13 and sixteen by day 20 (maximum sixteen). The combined footprint reaches 87 and 90, versus v8's hard production ceiling of 50 crops plus 18 animals. Final terminal footprints shrink substantially after harvest and abandonment: v8/COK end with 20/17 productive cells in 3001 and 22/15 in 3029. Terminal footprint alone would obscure the season's actual productive capacity.

COK fills its third plot faster while paying about 2,000 less for labor. This implicates both production ceilings and service efficiency; buying more land or workers alone is not an established solution. Whole-policy outcomes also change subsequent occupancy-coupled shop paths, so these observational comparisons do not identify the marginal cash return of the fourth plot.

## Smallest controlled expansion experiment

`scripts/phase4_land.py::build(mode)` constructs three isolated candidates from exact frozen v8. The original 48-game matched screen is complete; results follow below.

1. `land_only`: permit four total quadrants while retaining 50 crops, 18 shared animal places and 12 hands. This tests the extra capital/geometry cost without assuming productive capacity expands.
2. `crop70`: same commissioning rule, 70 crops, 18 shared animal places, 12 hands. This tests whether existing labor can service the additional production.
3. `crop70_hands14`: same 70-crop/18-animal plan with a 14-hand ceiling, preserving the existing workload-dependent hiring rule. This tests the interaction between productive capacity and labor, not a blanket hiring ramp.

All three retain the original first-land rule. Later quadrants can be commissioned once current production reaches 35 cells from day 10 (third total plot), or 60 from day 12 (fourth), as well as through the existing occupancy trigger. Later purchases require at least 2,500 remaining cash after the land price and already-planned obligations, or a larger existing feed reserve. That amount funds seed/service startup rather than treating newly unlocked cells as immediately productive. The original day-15 land cutoff, feed accounting, animal investment cap, action reservations and finite-season crop choices remain in force. Animal count is deliberately fixed to isolate crop-space commissioning before exploring another herd increase.

Three official-reset observation tests verify fourth-plot denial with insufficient working capital, permission with funded capacity, and refusal after the season cutoff. The candidates compile and Ruff passes. A small matched development screen should compare score, cash gap, new-quadrant fill time, harvested units, labor cost and missed feeding/watering before any larger test. The most informative comparison is `crop70` against both `land_only` and v8; the higher labor ceiling earns inclusion only if it turns otherwise missed work into realized saleable production.

```powershell
python scripts/phase4_land.py
python -m pytest tests/test_phase4_land.py
```

The diagnosis command reads existing manifests/replays and runs no games. Candidate construction is an explicit Python function and does not modify the deployed policy.


## Completed 48-game screen

The predeclared development panel uses seeds 3000, 3017, 3042 and 3063, both seats against each challenge opponent. Every variant actually buys all three additional plots in all sixteen games. Results include failed variants rather than selecting only the favorable land result.

| Variant | COK score | COK mean gap | Seyam score | Seyam mean gap | Mean peak productive tiles COK / Seyam | Mean labor COK / Seyam |
|---|---:|---:|---:|---:|---:|---:|
| Frozen v8 | 4/8 | -1,744.75 | 8/8 | +7,646.13 | 68 / 68 | -- |
| Land only | 5/8 | +4,120.63 | 8/8 | +13,562.00 | 68 / 68 | 7,936 / 8,224 |
| 70 crops | 3/8 | -4,330.00 | 2/8 | -2,096.13 | 87.38 / 87.13 | 7,936 / 8,224 |
| 70 crops, 14-hand ceiling | 1/8 | -4,828.25 | 3/8 | -4,508.38 | 88 / 88 | 19,126.75 / 19,945.88 |

These peaks are sampled daily, unlike the every-turn peak counts in the replay table above. Land-only improves paired mean gaps by 5,865.38 against COK and 5,915.88 against Seyam. The larger farm reaches its requested productive footprint but loses more often. Raising the labor ceiling adds roughly 11,000-12,000 labor expense without recovering the outcome deficit.

Across both opponents, land-only reduces successful movement from 4,192.13 to 4,010.25 actions per game, while successful harvest actions rise from 359.63 to 371.31 and feeding from 342.25 to 347.00. This is consistent with a geometric service benefit despite the additional 4,000 land expense, but it is not a causal decomposition: commissioning time, crop positions and occupancy-coupled shop paths all change. The 70-crop variant averages 4,168.31 moves and 383.56 harvest actions; the 14-hand version averages 4,634.56 moves and 411.69 harvest actions. Extra executed work alone does not imply useful net production.

All 48 games finish normally, with no candidate stderr or storage overflow. Land-only records zero nonterminal escapes and four water deaths. The 70-crop variant records seven escapes and six water deaths; its 14-hand version records three and six. Maximum recorded decision time is 179.9 ms; this is local execution evidence rather than a hosted guarantee.

Manifest: `data/raw/phase4-land.json`. Compact reproducible results: [phase4-land-screen-summary.json](results/phase4-land-screen-summary.json). Exact artifacts are `6c3d587de64242b3f6937b7b0aa2b4fc1369e21851a4539c78c82bcd401223af`, `1ee52659038f11ab1bafc45dc6b61aa1e9849afd091faccb6a088df5adc53296`, and `c66d066f20a645b0526c893cf55b0e094b307514c3ab956b7cc0f2677db4f67a` respectively.

A separately authorized 128-game known-data confirmation freezes land-only and uses seeds 3000 through 3031, both seats and both opponents. It tests whether the narrow improvement generalizes before attempting further geometric ablations. This remains development data and does not constitute fresh validation.

```powershell
python scripts/phase4_land.py --screen --output data/raw/phase4-land-reproduction.json
python scripts/phase4_land.py --summarize
python scripts/phase4_land.py --field --output data/raw/phase4-land-field-reproduction.json
```

The saved seed-3063 seat-0 counterfactual sharpens the geometric hypothesis. NE timing is unchanged, but the larger working-capital reserve delays SW from day 9 hour 16 to day 10 hour 17; SE arrives day 12 hour 20. At day 20 both policies have 68 productive cells. Land-only uses nine SE cells and reduces mean nearest-shed Manhattan distance from 3.647 to 3.265 steps. This supports examining closer replacement sites, not assuming earlier expansion explains every gain. [The saved geometry measurements](results/phase4-land-geometry.json) are regenerated by `--summarize`.
