# Joint maintenance feasibility on recorded losses

The banked-production candidate has a concrete admission defect: it calculates each animal's latest departure using the same available worker and carried wheat independently. A short route to each task does not imply that both tasks can wait. This differs from the spatial depot shortage already under investigation.

These are selected, known development observations from frozen v8 (`64fe3239…`), COK seeds 3029 and 3063, seat 0. No games were run. The solver reads only the chosen observation to construct its schedules. Recorded later actions and next-morning yield are used separately to diagnose displacement and compare outcomes. This is a feasibility test, not a cash or match-score experiment.

## Exact bounded calculation

At each selected hour, include every currently unwatered crop one miss from death, every animal one miss from escape, and every unfed animal whose banked bonus increases the next official daily yield. There is no truncation: the script rejects states exceeding eight tasks. The selected states have one to four tasks.

For every worker, enumerate task orders, an optional single depot visit, and all four access cells. Movement uses breadth-first search over official in-board moves; pickup and work each consume one action. A subset-partition dynamic program chooses nonoverlapping routes under the observed shared wheat budget, minimizing total actions. Carried wheat is specific to its worker. No purchases, future deposits, hires, market receipts or inter-worker transfers finance a route. The result is exact within this one-pickup route model; infeasibility does not rule out interventions involving transfers, purchases or earlier departures.

Execute the selected action sequences through official `_apply_unit_action`, then official plant and animal daily refreshes. All feasible witnesses pass their feeding/watering assertions. Unassigned workers PASS in this isolated verification; this intentionally establishes resource feasibility without claiming preservation of the entire farm's production.

| Recorded state | All selected obligations feasible? | Total worker actions | Existing depot wheat used | Urgent crop survival tasks |
|---|---:|---:|---:|---:|
| 3029, day 8, hour 16 | Yes | 8 | 1 | 0 |
| 3029, day 8, hour 18 | Yes | 6 | 1 | 0 |
| 3029, day 8, hour 20 | No | — | — | 0 |
| 3063, day 11, hour 16 | Yes | 8 | 1 | 0 |
| 3063, day 11, hour 18 | Yes | 10 | 1 | 2 |
| 3063, day 11, hour 20 | No | — | — | 2 |

## A joint reservation is necessary in seed 3063

At day 11, hour 18, the two sheep at (4,0) and (4,1) each hold three banked wool units. Worker 11 is at (4,1), carrying one wheat. The shed holds one wheat. Worker 2 is at (4,3). The following simultaneous schedule fits the six remaining actions:

| Worker index, including farmer as 0 | Actions from hour 18 |
|---|---|
| 0, at (2,2) | WATER |
| 2, at (4,3) | SOUTH, PICKUP WHEAT 1, NORTH, NORTH, NORTH, FEED |
| 7, at (1,3) | WATER |
| 11, at (4,1) | NORTH, FEED |

The WATER actions preserve both currently endangered crops. The two FEED actions preserve six banked wool units relative to no service. The recorded continuation already preserves one sheep's three units, so the incremental next-morning difference is **three wool**, not six. At the observed quote this is 492 gross cash before price impact, future collection/sale costs and displaced work. Wheat costs 36 at that observation. These are valuation bounds, not realized income.

The reproducible probe calls the exact corrected banked candidate `401b58a64d12a3df82ae9157a8d12a0d1e99c10c273fecb96f0d399501a9c6d4` and captures its local admission state. It returns the original v8 action here and assigns **no deadline routes**. Both sheep pass the valuable-production predicate. `safe_nightly` is true, total carried inventory is 11, and cash is 10,779: the cargo or working-capital guard is not responsible.

Instead, worker 11 independently makes (4,0) appear to require two actions, leaving four actions of slack, and (4,1) appear to require one action, leaving five. The `slack <= 3` condition rejects both reservations. Those two optimistic estimates reuse the same worker's sole wheat. The feasible global assignment needs worker 2 to leave for the depot immediately, with zero spare actions. By hour 20, the observed remaining input locations no longer permit all obligations to finish.

The actual worker-2 continuation is SOUTH, PICKUP WHEAT 1, SOUTH, SOUTH, SOUTH, FEED: it services a southern cow instead. The actual worker-11 continuation is FEED, CARE, then four PASS actions. Consequently the proposed rescue replaces cow feeding and one sheep CARE action as well as changing routes. It cannot be treated as a free three-wool gain. The two urgent WATER actions are already the baseline's first actions and require no displacement; those workers remain free afterward in a deployable scheduler.

## Seed 3029 distinguishes missing admission from contention

At day 8, hour 18, the farmer is at the depot and can PICKUP one wheat, move NORTH four times and FEED the sheep at (4,0) exactly by the deadline. This retains three additional wool, worth at most 681 at the current quote; wheat is 33. Baseline instead picks up two wheat and walks to a goose, then feeds and cares for it. The banked candidate already admits the sheep rescue at both hours 16 and 18. This case therefore supports the existing banked-production predicate, not a new joint algorithm. Its broader screen nevertheless failed to improve COK score.

## Implementation implication and limits

A useful next intervention would compute feasible *joint* allocation of valuable near-deadline feeding and endangered watering tasks before deciding that any task can wait. Reserve distinct workers and carried/depot units across the set, then emit only the first actions and replan. Do not advance every feed deadline indiscriminately: the earlier daily-feeding experiments lost crop maintenance and harmed match outcomes.

The exact calculation here supplies a concrete counterexample to independent route-slack admission. It does not establish how frequent this defect is, whether a broader planner repays displaced cow feeding/care, or whether it improves COK across seeds. Current-state crop-death obligations are protected, but ordinary watering, newly planted crops, harvesting, care, delivery and later inventory overflow are outside this small task set. Full-policy evaluation must measure those costs. A fixed six-hour reservation threshold could hide this instance while reproducing the same resource-contention error elsewhere.

Reproduce the six observation probes and candidate-admission checks:

```powershell
python scripts/phase4_joint_diagnostic.py
ruff check scripts/phase4_joint_diagnostic.py
```

The compact result is [phase4-joint-diagnostic.json](results/phase4-joint-diagnostic.json), including replay hashes, interpreter hash, complete action schedules, captured candidate admissions and displaced recorded actions. The official interpreter hash is `bc8a54879ef02c7ea64b8b333d6a976f0ea65c4949149d01f463f23bccee653e`. All six probes completed; four feasible witnesses passed official transitions. The new script passes Ruff.

## Bounded joint-assignment experiment

`scripts/phase4_joint_feed.py` implements min-cost flow over carrying workers, shared depot wheat, empty workers and valuable feed targets. Each worker can reserve one target; each depot unit can fund one pickup. Escape survival has lexicographic priority over healthy-animal production, then completed task count, then route cost. Existing cargo/storage safeguards remain active. Only after computing joint routes does the existing three-action slack trigger decide which first actions require reservation. Crop watering still uses ordinary assignment; this is not the full feed-and-water diagnostic optimizer.

The original greedy prepass remains the ready fallback if the flow search exceeds its budget. Six tests cover distinct worker/depot allocation, escape priority, cargo protection, forced-budget fallback without mutation, both source builds, and repeated first-action replanning through official transitions. In the six-action witness, worker 11 feeds the northern sheep while worker 2 collects wheat and feeds the other by hour 23.

The authorized 32-game development screen uses seeds 3000, 3017, 3042 and 3063, both seats, the same COK and Seyam pins, with four workers. It tests joint assignment on banked production alone and on banked production plus depot reserves. Each row compares against its own exact underlying policy on matching scenarios.

| Base → joint variant | Opponent | Base score | Joint score | Base mean gap | Joint mean gap | Paired gap change |
|---|---|---:|---:|---:|---:|---:|
| Banked → joint banked | COK | 4/8 | 6/8 | -2,087.50 | +2,750.25 | +4,837.75 |
| Banked → joint banked | Seyam | 8/8 | 8/8 | +9,480.88 | +8,673.25 | -807.63 |
| Banked + depot → joint + depot | COK | 6/8 | 6/8 | +8,132.88 | +6,774.38 | -1,358.50 |
| Banked + depot → joint + depot | Seyam | 7/8 | 7/8 | +7,359.75 | +7,670.50 | +310.75 |

The effects are not additive: joint assignment improves the banked policy's COK score here, while adding it to depot reserves reduces COK cash margin without changing score. All games ended DONE/DONE; neither joint variant had nonterminal escapes or overflow. Joint banked had seven water deaths across sixteen games, and joint depot had six. The highest decision duration was 94.0 ms. These four previously tuned seed clusters do not establish generalization or justify promotion.

The screened hashes are `ecd510b27ebd7dbecee158c3687e322670b35cfc24d2eb59f981131bbd2707a3` (banked) and `f99a5d18c21f93ed64a31c53f9277ae0174edba7f211135a1bb2f20291fc4dd7` (depot). They used a six-millisecond flow budget. There were eleven stderr turns: eight in joint banked, three in joint depot. The benchmark saved counts without message text, so these cannot retrospectively be certified as budget fallbacks, although the new explicit fallback message is a plausible explanation. Zero fallback/error-frequency claims are unsupported.

Before broader study, the flow budget was increased to 50 ms while retaining checks during the search and the cheap fallback. This changes no objective or route constraint. New hashes are `3d84e710ca80cf761918200746632d895cb9d4911d8fd4f43d924d6cc025fd57` (banked) and `e378d7f718fe127c3c2140e8a4c58bfe3ae0ee415244effbd5141084bd605218` (depot). Twelve saved-observation comparisons, covering both variants and all six diagnostic states, return identical actions between budgets with no stderr. This is limited budget-change parity, not a claim that complete trajectories cannot diverge under runtime pressure. The old `--budget 0.006` builds reproduce both screened hashes exactly. Subsequent evaluations must identify the new hashes and retain actual stderr messages.

Reproduce or inspect without rerunning games:

```powershell
python -m pytest tests/test_phase4_joint_feed.py
python scripts/phase4_joint_feed.py --verify-budget
python scripts/phase4_joint_feed.py --summarize --budget 0.006
```

To reproduce the original screen, use a new output path:

```powershell
python scripts/phase4_joint_feed.py --budget 0.006 --workers 4 --output data/raw/phase4-joint-feed-reproduction.json
```

The complete compact archive is [phase4-joint-feed.json.gz](results/phase4-joint-feed.json.gz); the [matched summary](results/phase4-joint-feed-summary.json) checks source hashes, opponent hashes and effective configuration against both base panels. Budget-change evidence is [phase4-joint-budget-parity.json](results/phase4-joint-budget-parity.json). No joint policy has been promoted on this screen.

## Broader field result: rejected

The 50 ms joint-banked artifact (`3d84e710…`) was subsequently evaluated on all 32 known development seeds 3000–3031, both seats, against both challenge opponents: 128 games. The exact frozen v8 rows on matching scenarios are the comparison baseline. This is development confirmation, not fresh validation or holdout.

| Opponent | Frozen v8 | Joint banked | v8 mean cash gap | Joint mean cash gap |
|---|---:|---:|---:|---:|
| COK | 21/64 | 15/64 | -4,732.42 | -5,671.95 |
| Seyam | 59/64 | 61/64 | +16,608.72 | +17,084.06 |
| Equally weighted two-opponent pool | 80/128 | 76/128 | — | — |

The targeted fix does not generalize to the main failing matchup. It is rejected despite its physically correct rescue witness and encouraging four-seed screen. This comparison measures the full banked-plus-joint package against v8; the earlier exact-base comparison isolates the joint component only on its smaller panel. No claim of an isolated broad joint-assignment effect follows from this table. The strict matched result, including paired uncertainty, is [phase4-joint-field-summary.json](results/phase4-joint-field-summary.json).

All 128 games completed, but runtime fallback remains observable: **45 exact `joint_feed_fallback: budget` messages**, now preserved by the evaluation harness. Maximum complete policy action duration was 266.461 ms. The 50 ms search limit does not bound the entire policy call, and wall-clock checks can include process scheduling delays. These fallbacks must not be described as zero-error deterministic execution.

## Bounded solver profiling

To investigate the fallback, profile the unchanged frozen helper over every nonterminal observation in the completed seed-3002 COK and Seyam seat-0 replays. No games are run and no match outcomes are used for selection. On this serial recorded-observation pass, all **1,392 calls** complete without fallback or stderr, with up to 17 pending animals and 13 workers. Each returned assignment passes unique-worker, unique-target, shared depot wheat and deadline assertions.

The saved pass has median helper wall time 0.038 ms, empirical 99th percentile 0.607 ms and maximum 22.138 ms. An earlier local probe of the same observations peaked at 1.188 ms. The dense state producing the larger outlier contains 14 targets; it is not consistently slow across runs. Windows process CPU time is quantized too coarsely for these calls to reliably attribute the difference to CPU work versus scheduling. No predecessor-cycle or persistent slow-state reproducer was found. Scheduling pressure or allocation/collection overhead are plausible explanations; neither is proven by this profile.

The implementation performs at most one successful augmentation per available worker, with bounded Bellman–Ford passes per augmentation and in-search wall-clock checks. There is no evidence here justifying another budget increase or gratuitous solver rewrite. A future promoted policy would still need controlled-load runtime checks, retained fallback messages and full artifact trajectory qualification. This candidate is already rejected on performance grounds.

```powershell
python scripts/phase4_flow_profile.py
```

The [saved profiling results](results/phase4-flow-profile.json.gz) pin the source and both replay hashes and preserve every measured call. Profiling does not alter the experimental source hash.
