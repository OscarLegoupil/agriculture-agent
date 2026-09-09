# Second competitive cycle

## Incumbent and data boundary

Branch `feat/competitive-agent-v2` starts from `48f576f8d781785b90639d2072fd484acab8fd00`,
the unmerged first-cycle branch in PR #65. The rollback artifact is unchanged:
`submissions/20260909-v7/main.py`, SHA-256
`750f123073865347efd3b9c4b72022ff9923f4130c929ac76c1b0742374b09ee`.
Its policy source was frozen at `4eac236`; configuration is embedded in those
exact bytes. Source snapshots and the first-cycle evidence remain preserved.

The incumbent improved production scale and coordinated execution. It passed
the old local holdout gate at 65.23% against the equal-weight lonespear/GzmCR
pool. This is not a live rating. The 128 old holdout seeds, 10000–10127, are now
known development data, as are the original 16 development seeds and validation
1000–1063. They must never be represented as fresh evidence again.

## Protocol before second-cycle selection

The frozen anchor pool retains lonespear `774b260`, GzmCR `6a76335`, and the
supplementary TinaawhyteD `169ca94`. Its primary weights remain 0.5/0.5/0.
An evolving challenge pool will contain reviewed, qualified stronger public
agents, the incumbent, and supply stress variants. Freeze challenge membership
and weights before validation; derived implementations share a lineage and
must not masquerade as independent families.

Use cheap old-data screens first, normally 8–24 games per hypothesis. Expand
only changes supported by realized behavior and paired outcomes. Initial budget
is 400 screening/diagnostic games, extendable with a stated new question.
Independent research, economic probes and replay diagnosis have separate
bounded ownership. No new paid resources are authorized.

Second-cycle validation uses previously unused seeds 2000–2063, both seats.
Final holdout uses 20000–20127, both seats, unopened until release selection.
Run challenger and incumbent against identical opponent versions and scenarios.
Never compare their raw cash across different opponent responses as if the
opponent were fixed; these are whole-game policy interventions.

The interpreter shares a seeded daily RNG between weed spawning and shop
selection. Occupancy changes the number of weed draws, so a policy intervention
can also change future realized shops. Matched seeds preserve initial randomness,
not identical exogenous demand paths. New benchmark records include observed
shop sequences and market inventory/prices to make this consequence inspectable.
Never patch the interpreter to fix shop paths in deployable performance claims.

Practical promotion requires at least a five-percentage-point improvement on
the anchor primary score, a positive lower 95% paired-seed bound on that
improvement, and no independent anchor family below 40%. The challenge pool
must show a positive paired score improvement and a score of at least 50% on
its predeclared primary weighting. Require zero candidate execution errors and
timeouts, source/artifact parity and verified runtime headroom. Report failures
of these criteria without changing weights or removing difficult opponents.

Use 10,000 deterministic bootstrap resamples of complete seeds, retaining both
seats, all opponents and both candidate identities. Report score, paired delta,
cash gaps (mean, median, 10th percentile), errors, fallback counts and runtime
quantiles. Opponent coverage uncertainty is separate from seed uncertainty.
Validation selects candidates; a single frozen candidate receives final holdout.
If holdout informs changes, retire it and name a new untouched split.

Kaggle CLI again reports authentication required. No submission or legal-terms
acceptance occurred. Local work continues; hosted compatibility and rating
remain unverified until authenticated access is available.
