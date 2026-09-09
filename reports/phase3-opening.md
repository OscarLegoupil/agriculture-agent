# Financing production before expanding the herd

The phase-2 challenger established a larger farm but still won only 3/128 COK
validation games. This continuation tests startup cash flow and executable crop
cohorts against the unchanged, pinned COK and Seyam references. All results below
are exploratory development results, not fresh validation or leaderboard evidence.

The opening establishes seven wheat tiles and a first melon cohort with two cows
and two sheep. Wheat supplies working capital before the melon harvest. Later
planting emphasizes recurring strawberries while their finite remaining season
can still repay the investment. The controller restricts fertilizer to recurring
crops; its previous annual applications usually followed WATER and missed that
action's immediate growth benefit. Fertilizer reserves now cover upcoming useful
applications rather than counting all planted tiles, including immature crops.

These choices interact. On seeds 0 and 2001, both seats:

| Change from frozen `0098` | Seyam wins / 4 | COK wins / 4 | Mean COK cash gap |
|---|---:|---:|---:|
| Recurring-only fertilizer | 0 | 0 | -37,578 |
| Crop-financed opening, previous fertilizer execution | 2 | 0 | -16,127 |
| Opening + recurring-only fertilizer | 4 | 0 | -12,186 |
| Above + near-term fertilizer reserves, 12-hand cap | 4 | 2 | +640 |
| Above with 10-hand cap | 4 | 2 | -341 |

The combination matters: removing annual fertilizer alone is insufficient. With
the new opening, annual fertilizer purchases cost roughly 14,000 per COK game;
the recurring-only combination reduces that expense to roughly 482. This is an
observed whole-policy effect, not an assertion that every avoided purchase would
otherwise be pure waste. A separate counterfactual tests correctly ordered annual
applications with explicit marginal yield and opportunity costs.

On four additional development seeds (5, 11, 17, 42), the 12-hand policy won 7/8
against Seyam and 2/8 against COK. The 10-hand policy won 8/8 and 3/8 respectively.
Across all six seeds the latter is 12/12 against Seyam and 5/12 against COK. The
small panels cannot establish a reliable population advantage for a labor cap.
Identical outcomes in both seats on some seeds are dependent observations.

A separate herd screen changes the mature herd after the same day-8 expansion
gate. Six cows/two sheep performs worse than ten or fourteen cows/two sheep;
adding eight geese to the smaller herd does not close the COK gap. Fourteen
cows/two sheep wins 2/4 COK games with a +6,912 mean gap, but has not yet received
broader confirmation. Buying more animals is therefore a hypothesis, not a
selected production rule. Replay diagnosis instead points to *earlier* funded
cow cohorts as a more direct way to recover missing milk production.

The official generator's weed draws depend on occupied tiles before shop draws.
Changing farm decisions can therefore change future shops on the same seed.
These comparisons measure full-policy interventions, including opponent response;
they do not hold future demand realizations fixed.

Reproduce the screens with `scripts/phase3_startup.py` and
`scripts/phase3_herds.py`. Exact executable snapshots and per-game records are
indexed by `reports/results/phase3-development.json`; all frozen versions remain
available under `reports/sources/`. The deployed v7 and experimental `0098`
artifacts remain unchanged. New validation is reserved for seeds 3000–3063 and
the unopened holdout remains 20000–20127.
