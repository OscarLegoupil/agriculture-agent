# Animal admission objective: capital return or cash per slot?

Changing the existing model's ranking to absolute net cash improves the measured
four-seed screen, but the improvement includes a changed opening purchase order.
The more complex scenario model does not gain match score from this objective
change. Neither result establishes superiority on a fresh field.

## Exact intervention

`scripts/phase3_objective.py` reads two immutable source snapshots, verifies their
hashes, and changes exactly one expression:

```python
options.append((net / cost, animal))
# becomes
options.append((net, animal))
```

Affordability, cash reserves, pending purchases, eighteen herd slots, scheduler,
forecast formulas and other parameters remain byte-for-byte unchanged. The
builder reverses that substitution and asserts equality with the original
source. There are no new game-model formulas requiring additional interpreter
contracts in this ablation.

The hypothesis is that when animal slots are scarce and funding is available,
net cash per slot can be more relevant than profit per unit of purchase capital.
The hypothesis is not universal: early cash is scarce, higher-cost animals have
different startup delays, and a sheep can demand different worker time from a
goose. A cash guard verifies affordability, not the shadow price of liquidity,
land, travel or worker capacity. Neither greedy ranking solves joint constrained
investment optimally.

## Matched development evidence

Each row uses the same pinned Seyam and COK opponents, seeds 2000, 2003, 2009 and
2013, and both seats. The two new candidates add 32 games on known development
data. Both complete all games with zero stderr turns. No validation or holdout
is consumed.

| Model and objective | Seyam wins / 8 | Mean Seyam gap | COK wins / 8 | Mean COK gap |
|---|---:|---:|---:|---:|
| Existing model, net/cost | 8 | +13,765.88 | 2 | -3,879.25 |
| Existing model, net cash | 8 | +32,740.75 | 4 | +129.75 |
| Scenario model, net/cost | 8 | +22,244.88 | 2 | -5,167.88 |
| Scenario model, net cash | 7 | +21,229.38 | 2 | -833.50 |

The existing model's mean paired cash-gap changes are +18,974.88 against Seyam
and +4,009.00 against COK. The COK gains add both 2013 wins; it still loses both
seats on 2000 and 2009. Its equal-opponent score increases from 62.5% to 75% on
this inspected panel, with only four underlying seeds.

The scenario model's mean COK gap improves by 4,334.38, but its two 2003 wins
become losses while both 2013 losses become wins. It also loses one Seyam game.
Its equal-opponent score falls from 62.5% to 56.25%. Higher candidate cash or a
smaller mean deficit is insufficient to justify selecting this extra model.

## Opening divergence limits the causal conclusion

The ranking applies from the first admission, not just after day 8. Both versions
still establish twelve melons, seven wheat, two cows and two sheep on day 0, but
the cow/sheep placement order changes. In the seed-2000 comparison against Seyam,
day-1 cash is 32 for both; day-2 cash differs by one, and by day 3 the wheat cohort
already differs. Thus later differences cannot be attributed solely to removing
a cheap-animal bias when eighteen slots bind. They also include geometry,
early servicing, and subsequent demand changes through occupancy-dependent
random draws.

This is a clean one-expression **whole-policy** ablation, not an isolated
mature-herd experiment. The promising existing-model result merits comparison
on a broader known panel or a separately declared intervention preserving the
opening. It does not justify silently claiming an optimal per-slot objective.
No additional tuning or games are included here.

## Artifact and runtime record

| Variant | Exact SHA-256 | Maximum action time |
|---|---|---:|
| `capacity_net` | `0595c42ce3f38ff064c717e6a50529fa33c3966c2aadc9d0714028f99a071998` | 77.52 ms |
| `scenario_net` | `f0894e606dc6e6845abbbcb3a1ed0d27b7b50f52aac822a43223d581e8dc2d14` | 74.52 ms |

The respective parents are
`521467d45a0e2739d634ec628009753fe8e3844633bdc6e6f733f45521489a59` and
`6750ea481374fb52393a1f941c9d3b4b7fc54d33d6ab46a0351d7dfb75602ba5`.
All executable bytes remain under `reports/sources/`. The complete provenance,
configuration, daily behavior and paired results are saved in
[`results/phase3-objective.json.gz`](results/phase3-objective.json.gz).

```sh
uv run python scripts/phase3_objective.py --workers 3
```
