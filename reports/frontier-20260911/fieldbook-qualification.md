# Six-Day Fieldbook qualification

The frozen `fleet_cereal` candidate beat Six-Day Fieldbook in both seats on
development seed 5000. V8 and the earlier fleet candidate lost those same seats.
This is an informative challenge screen, not validation across seeds or evidence
of a live leaderboard rating.

| Our policy | Seat 0: ours / Fieldbook | Seat 1: ours / Fieldbook | Match score | Mean cash gap |
|---|---:|---:|---:|---:|
| V8 `64fe3239` | 47,960 / 67,433 | 48,740 / 68,320 | 0/2 | −19,526.5 |
| Fleet `9400f9b0` | 68,118 / 79,971 | 81,629 / 86,853 | 0/2 | −8,538.5 |
| Fleet cereal `c2b3162d` | 123,736 / 71,220 | 163,777 / 73,179 | 2/2 | +71,557.0 |

The [saved results](../results/breakthrough-sixday-screen.json) contain exact
candidate hashes, paired outcomes, runtime, income, shops and replay hashes. These
games remain separate from the COK/Seyam historical pool and the Mooman panel.
One seed cluster does not support a useful confidence interval.

## What this result establishes

The cereal variant's main revenue source here is **tomato**: 73,668 and 111,394,
compared with wheat revenue of 7,636 and 7,955. It bought 23 tomato seeds in each
game. This result cannot be attributed to wheat throughput alone.

The official trajectories also produce different shop sequences. Cereal receives
three early pizza shops, fleet receives two, and V8 receives none among its first
five shops. The common seed does not fix future shops when changed farm activity
changes weed draws. These are legitimate policy outcomes, but this small screen
does not separate production improvements from favorable demand. Further testing
needs varied seeds and opponents that supply tomatoes.

All six games completed normally. Cereal had no reported fallback, a maximum
decision time of 30.591 ms and a worst per-game p99 of 19.375 ms. Fleet reported
one budget fallback. Fieldbook reported no stderr across 4,314 decisions; its
maximum was 14.938 ms. Cereal still lost 11 and 16 animals before the terminal
window. This qualification did not classify their causes; the counts alone do
not establish scheduler defects.

## Source and execution

[Yusuke Hayashi's public notebook](https://www.kaggle.com/code/yhay81/six-day-public-state-fieldbook)
is pinned to notebook 132897306, version 3, last run September 8, 2026. Its
[source dataset](https://www.kaggle.com/datasets/yhay81/six-day-public-state-agent-source)
is pinned to version 1. All seven published source hashes matched before build.
The supplied code is unchanged; `main.py` is an exact copy of `agent_main.py`.

Fieldbook selects six-day public-history action blocks using observable state.
It belongs to the same broad replay-tape family as Mooman/COK/Seyam, despite
different implementation and routing. Its cached notebook score and
author-reported broad-pool results are not treated as verified competitive
strength. The [reference manifest](fieldbook-reference.json) records provenance,
license evidence, compiler, native dependencies and executable hashes.

Qualification used Ubuntu WSL, Python 3.12.3 and `g++ 13.3`, with the published
build command. The official `kaggle-environments==1.32.7` interpreter hash matches
the Windows experiments. Clean-directory loading, both seats and repeated
step-zero calls passed. The ELF library is not Windows-native; hosted Linux
compatibility has not been tested.

The [deterministic archive](fieldbook-reference.tar.gz) preserves the complete
source, compiled library, original notices, Apache-2.0 license and provenance.
Its SHA-256 is
`25c3ed0461aecb307c522742c87b03b01d57392539cc8ac549d12f84e4b3bf44`.
The native library hash is
`a59679c4c6344581810bf48557440f614954b68a425a69ed1d22dbc1ac7c9aa9`.

On Linux/WSL with the repository dependencies installed, restore the isolated
opponent and run the V8 smoke panel from the repository root:

```bash
python -c "import tarfile; tarfile.open('reports/frontier-20260911/fieldbook-reference.tar.gz').extractall('data/raw/reference-sixday', filter='data')"
python scripts/benchmark.py --candidate submissions/20260909-v8/main.py --opponents data/raw/reference-sixday/main.py --seeds 5000 --workers 1 --output data/raw/sixday-reproduction.json
```

Use a new output filename for each run. The standard harness omits shared
libraries from its dependency manifest; retain the committed reference manifest
alongside its output and verify `agent.so` against the hash above. Qualification
recorded the complete native bundle separately before and after each panel.
