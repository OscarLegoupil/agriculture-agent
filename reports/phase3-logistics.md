# Delivery and input service experiments

These experiments start from the exact expanded challenger
`0098d9e4f77e2420cb4a09abd47e49f5160009cd0818ae37a793bc3e419ffc4b`.
They use known seeds 0 and 2001, both seats, against the pinned COK and Seyam
references. Seed 2001 belongs to the now-inspected phase-two validation set;
these are development counterfactuals, not fresh validation or holdout.

## Replay evidence and hypotheses

In the challenger/COK seed-2001 seat-0 replay, a conservative count finds 255
mandatory return moves and 65 DROP actions while cash is at least 2,000 and
combined shed/carried goods are below 80. This count requires at least five
carried non-input products and excludes wheat/fertilizer-only loads. It shows
potential for free end-of-day transfers to replace discretionary deliveries;
it does not prove that waiting preserves sale prices or working capital.

The first candidate therefore defers ordinary returns while cash covers
near-term feed and labor and storage is below 80 units. It retains low-cash,
capacity-pressure and final-day returns. Input batches are bounded by nearby
same-input services, distance from the shed, and remaining working time.
Storage reservations continue to use observed stock without crediting planned
deposits or pickups in the wrong interpreter order.

The second candidate ablates changed input batching, keeping original pickup
quantities with the same pressure-aware delivery policy. The third tests a
different, more specific mechanism: original return timing with selective
PLACE of sellable products, retaining carried inputs needed by outstanding
tasks. Final-day liquidation still uses DROP; capacity is reserved only for
the amount actually deposited. It uses original pickup quantities.

An observed-state check demonstrates the selective action: on day 11, hour 12,
worker 10 carries two wheat and six melons. The candidate emits
`PLACE MELON 6`, retaining feed instead of unloading everything. The official
interpreter supports this product-deposit form of PLACE.

## Complete screens

Each candidate runs eight complete official games, four per opponent. The
nightly ablation and selective-deposit extension bring this study to 24 games.
Baselines are matching 0098 records from the completed development and
validation manifests, not different versions or seed sets.

| Candidate | COK wins / 4 | COK paired mean-gap change | Seyam wins / 4 | Seyam paired mean-gap change |
|---|---:|---:|---:|---:|
| Pressure-aware delivery plus service batches | 0 | +14,339 | 0 | −25,642 |
| Pressure-aware delivery, original batches | 0 | −891 | 1 | −8,303 |
| Selective product deposits, original timing/batches | 0 | +1,973 | 1 | −1,338 |

The baseline mean gaps are −49,613.75 against COK and −3,503 against Seyam.
No candidate is promoted. Four games per opponent cannot support a reliable
generalization claim, and all twelve COK games lose.

The first candidate substantially reduces COK-facing DROP actions from 163.75
to 68.5 and pickups from 199 to 152.75, but travel barely changes, 4,220.75 to
4,196.75, while idle actions increase from 611 to 758.75. Its own final cash
falls by 5,849.75; the improved cash gap comes from a larger opponent decrease.
This is a whole-policy effect including changed market behavior and potentially
changed shop paths, not evidence that saved transport increased income.

Selective product deposits are less disruptive. Against COK they reduce
pickups to 188.25 and DROP actions to 145.5, with travel 4,201 and idle actions
604. The intervention is mechanically useful but too small and inconsistent
to establish a meaningful competitive gain by itself. Against Seyam its
pickups fall from 200.25 to 188.75 while travel remains approximately unchanged.

The critical distinction is between eliminating an operation and using the
freed action productively. The current immediate assignment often leaves that
capacity idle or redirects it without increasing valuable output. These
results reject blanket deferral of delivery as a solution and motivate testing
executable service routes with explicit production obligations if further
schedule-level changes are pursued. Earlier sale opportunities and liquidity
remain real economic benefits; free nightly transfer is not automatically best.

All 24 games complete with zero failed worker actions and no stderr/fallbacks.
Maximum observed decision time is 99.94 ms. Overflow is zero throughout. One
service-batch game has a pre-terminal animal escape, so its losses must not be
described as entirely deliberate endgame abandonment.

## Reproduction and retained evidence

```powershell
uv run python scripts/phase3_logistics.py --name service_routes --output data/raw/phase3-logistics.json
uv run python scripts/phase3_logistics.py --name nightly_pressure --output data/raw/phase3-nightly-ablation.json
uv run python scripts/phase3_logistics.py --name selective_delivery --output data/raw/phase3-selective-delivery.json
```

The three complete manifests include exact executable hashes, compressed source
snapshots, interpreter/dependency provenance, daily production, cash ledgers,
worker actions, losses and runtime. The source builder restores the frozen
challenger snapshot rather than relying on a mutable development policy.
No deployed source or release artifact is changed.
