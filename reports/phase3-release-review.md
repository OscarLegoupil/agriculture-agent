# Independent release review

This review examined the consolidated policy against frozen development candidate `59b46457c6511d5df959a95a8c4eb8297e649e0a95b2ae7886f2042e7a60bab3`, then verified a consequential terminal-order correction before fresh validation. No additional benchmark matches were run for this review.

## Result and exact identities

The initial consolidated source had normalized SHA-256 `d7a816d4fa82be8a781c2d4c9ee845eb6062c8468cc3eb7013fb2c66cb45902a`. Consolidation folds identical final parameter overrides into the declaration, removes an overwritten forecast calculation, adds annotations and renames local variables. No observation-leakage or unintended strategic change was found in those edits. The separate saved-observation refactor-parity manifest provides the empirical comparison; static inspection alone is not trajectory equivalence.

The review found a terminal liquidation defect that also existed in the frozen candidate. Farmer plus twelve hands, all at shed access with one milk each on day 29 hour 22, emit thirteen DROP actions and thirteen separate SELL orders. The ten-order cap executes only ten sales, stranding three milk at the scoring boundary. This was reproduced on an official reset-derived observation.

The corrected final artifact is `submissions/20260909-v8/main.py`, SHA-256 `64fe323936dc9494add413eb956b0294658a88efe28572332c94676c68a09325`. It coalesces repeated product sales only on day 29 hour 22 and only when the pending order list exceeds the configured cap. First-seen product order is preserved; aggregation never moves sales across a non-sale operation. All earlier decisions and within-limit final orders retain their existing behavior.

`reports/results/phase3-liquidation-parity.json` compares this exact artifact against normalized `d7a816...` on ten saved replays, 7,190 observation/action pairs, both seats and all four reference families. No actions differed, including the final turns in those recorded trajectories. Those trajectories did not expose the synthetic saturation case; zero observed differences is not proof that every possible trajectory is unchanged. Fresh validation must therefore evaluate the corrected artifact, not attribute frozen-59b results directly to it.

## Interpreter-backed liquidation evidence

Four tests in `tests/test_terminal_liquidation.py` pass against the integrated source. Thirteen simultaneous milk deliveries and mixed milk/wool deliveries are completely sold under the ten-order cap. With a passive opponent, actual cash and market inventory exactly match unlimited split orders and the sum of official marginal quotes. A within-limit final order list remains separate.

Aggregation is not cash-equivalent against an active opponent. The interpreter quotes both players before either commits a unit, and changing order-batch boundaries changes that interleaving. In the constructed thirteen-milk-versus-thirteen-milk case, aggregation yields 1,753 cash to each player; unlimited split orders yield 1,590 to our player and 1,892 to the opponent, despite identical final market inventory. The test deliberately records this non-equivalence. Restricting the correction to otherwise truncated final lists avoids gratuitously changing valid order schedules, but competitive price effects still require evaluation of the exact final policy.

## Observation legality and economic limitations

The deployed module imports only the Python standard library. Decisions read the player's supplied private inventory/seeds, both publicly visible farms, current market and town, and configuration. It does not load reference executables, replay files, seed identities, random-generator state, private opponent inventories or future realized shops. Future demand averages over potential shop composition; that is an uncertain scenario assumption, not a realized future observation. Default market parameters are pinned interpreter constants used when the public observation omits parameters.

Economic values remain heuristics. They retain current asset ages and inventory, but do not solve a complete executable investment plan. Forecast animal care rates, future crop arrivals, feed costs and fixed worker-action charges can misprice displacement or saturation. The shared herd budget permits meaningful adaptation without demonstrating that its marginal values are calibrated in every demand regime. Fixed thirty-day/24-hour assumptions apply to the verified competition configuration; arbitrary custom season configurations are not supported.

## Runtime, exceptions and fallback

The assignment optimizer prepares a valid greedy assignment before entering augmenting-path search and checks a 150 ms budget during that search. Budget fallback writes `assignment_budget_fallback` to stderr. `tests/agent/test_competitive.py` verifies the forced-budget fallback and distinct destination assignments.

There is no blanket exception handler silently replacing errors with PASS. Missing farms or an invalid player produces the documented cheap empty-observation fallback; unexpected malformed fields or other exceptions propagate to the environment and can be counted as failures. This favors visible defects during development, but it is not a general exception-recovery policy.

The 150 ms guard is local to optional assignment search, not a watchdog around the entire decision function. Forecasting, task construction, deadline routing and greedy fallback construction execute outside it. Their loops are bounded by season, board, animals and workers, but a hard whole-policy timeout guarantee is not established. The frozen-59b 128-game manifest reports all matches DONE, zero stderr turns, maximum decision time 73.266 ms and maximum per-game p99 9.853 ms against the configured one-second action limit. These are local measurements for that hash; the release's packaging/runtime checks and fresh evaluation must establish its own evidence. Hosted runtime remains a separate verification.

## Reservations and remaining scheduling risks

The policy reserves shared seeds, tasks and pickup stock without crediting a later worker's DROP as an earlier worker's available input. The feed-deadline prepass reserves an animal/worker and a wheat unit while allowing a feasible pickup-and-feed route to supersede product delivery. Constructed official-state tests verify scarcity handling, retained milk cargo and rescue timing. The saved escape witnesses demonstrate why this correction is needed.

These reservations do not constitute a complete route plan. Assignments are recomputed each turn; future task interruptions can invalidate an initially feasible route. The nightly-capacity check covers currently held inventories, not all future harvests, and input availability in aggregate is not equivalent to timely delivery to every tile. Annual watering admission checks an available approach distance but does not reserve a complete water-harvest-delivery chain against all competing workers. Capacity saturation, simultaneous crop deadlines and terminal travel remain possible losses. Local deadline fixes should not be described as eliminating every missed deadline.

## Release conditions and reproduction

The identified order-cap defect is corrected and its tests pass. No additional legality blocker was found in this review. Release evidence must still use artifact `64fe323...` consistently for clean-directory packaging, fresh validation, any holdout and hosted submission. Historical packaging manifests for other hashes are not evidence for this artifact. Local development improvements do not establish a high live leaderboard rating or broad robustness against unrepresented strategies.

```powershell
python -m pytest tests/test_terminal_liquidation.py tests/test_phase3_harvest.py tests/test_phase3_deadlines.py
python scripts/phase3_liquidation_parity.py
```

The parity command reads the archived normalized pre-correction source and ten already saved replays listed in the refactor-parity manifest. Optional `--reference`, `--artifact` and `--output` arguments make the compared identities explicit. It performs no simulation games. Reviewed source snapshots, final-order measurements and interpreter-backed tests preserve the distinction between established behavior and untested generalization.
