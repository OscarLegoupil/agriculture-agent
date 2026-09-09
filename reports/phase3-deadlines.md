# Feed deadlines include acquisition and arrival

The saved frozen-opening replay against COK, seed 2009 seat 0, contains two avoidable nonterminal escapes despite available feed and ample cash. The narrow deadline intervention removes both in a full official match, but the sixteen-game screen does not establish a material overall competitive gain.

## Exact precursor decisions

On day 16, the sheep at (9, 0) has already missed one feeding day. At hour 14, worker 6 stands at shed access (5, 4), carrying six milk, with five wheat in the shed and 22,068 cash. It performs DROP, then PICKUP at hour 15. Its eight subsequent movement actions reach the sheep on hour 23, leaving no action for FEED before the daily escape transition. PICKUP at hour 14 followed by the same direct route and FEED at hour 23 is legal and preserves the milk inventory for later delivery. The official daily animal transition then produces three wool and preserves the sheep.

On day 19, the cow at (7, 1) is also one missed feeding day from escape. Worker 10 stands at shed access (4, 4) at hour 14 with one fertilizer, three shed wheat and 35,708 cash. It moves WEST, reverses EAST, and picks up feed at hour 16. After feeding another threatened cow at (6, 3), it arrives at (7, 1) on hour 23, again one action late. Picking up two wheat at hour 14 can feed both cows by hour 22. Official copied-state execution verifies both survive, each producing two milk at the daily transition.

`scripts/phase3_deadline_diagnosis.py` reproduces these local witnesses from the saved observation. Other actors and the market are held inactive in those witnesses: they prove physical feasibility, not an entire changed match trajectory. The artifact records the replay SHA-256 and preserves the worker's original cargo.

## Small intervention

The candidate reserves threatened animal feed routes when the best feasible worker has at most three actions of slack before midnight. Route cost includes movement to a shed access tile, PICKUP, movement to the animal, and FEED after arrival. Each selected worker and animal are excluded from ordinary matching that turn, and one shared wheat unit is reserved even while the selected worker approaches the shed. Replanning from the next observation handles completed or invalidated actions.

This prepass can bypass automatic product delivery only when cash is at least 1,000 and the current total carried and shed inventory fits the shed capacity. It does not assume future collections will fit, change all nightly deliveries, or apply after day 28. Existing useful-production filtering still controls which FEED tasks are generated. The fixed hour-15 deadline boost alone could not represent the eight-step shed-to-sheep trip.

Actual-policy checks on the two recorded observations select legal PICKUP actions before the last feasible departure and verify official survival. A separate clean-checkout test constructs two threatened animals from the official reset state, verifies feed acquisition while preserving six carried milk, replays both routes, and checks scarce shared-stock reservations. They also check same-turn wheat pickup totals and unique urgent task reservations. On the day-16 snapshot, the policy finds an equally feasible farmer route rather than requiring worker 6's identity. The deployable implementation reads only the current legal observation.

## Matched sixteen-game development screen

Base: `febe9c76051a11e9ea7700e2d4701722e98274c51c50874ad03e1088b9398d4b`.
Candidate: `298602f62772a7a523a4fb29fa0726a884526cb9e0b584f43ecd92f41f6fe1cf`.

Pinned COK and Seyam, known seeds 2000, 2003, 2009 and 2013, both seats; official environment 1.32.7. Base records are `data/raw/phase3-opening-field.json`, candidate records `data/raw/phase3-deadlines.json`. Four seed clusters are a screen, not validation or evidence of leaderboard strength.

| Opponent | Base wins | Candidate wins | Base mean gap | Candidate mean gap | Paired gap change | Base early escapes | Candidate early escapes |
|---|---:|---:|---:|---:|---:|---:|---:|
| COK | 0/8 | 0/8 | -29,958.25 | -29,635.88 | +322.38 | 7 | 1 |
| Seyam | 6/8 | 7/8 | +11,753.25 | +11,468.88 | -284.38 | 11 | 3 |

Equal-opponent mean gap improves only 19.00 cash. COK water deaths decrease from three to zero; Seyam water deaths increase from zero to two. Terminal escapes remain separate: COK ten before/after; Seyam four to thirteen. Deliberate terminal abandonment is not counted as an early execution failure.

Both early seed-2009 escapes disappear in the saved candidate replay. In seat 0, milk sales increase 218 to 226 and wool 85 to 92, but wheat purchases increase 171 to 193 and strawberry sales fall 246 to 239. The cash gap worsens from -41,516 to -42,089. Preserving an animal also preserves its future feeding obligations and can divert crop service; this is not free revenue. Changed farm occupancy can additionally alter the seeded shop path, so the matched cash difference cannot be assigned entirely to those quantity changes.

All sixteen matches completed normally, without candidate stderr; maximum measured decision time was 65.6 ms. The result supports a specific reliability correction, but not an assumption that it adds competitive value to another improved policy. Interaction tests must earn that conclusion.

```powershell
.venv/Scripts/python.exe scripts/phase3_deadline_diagnosis.py
.venv/Scripts/python.exe scripts/phase3_deadlines.py --check
.venv/Scripts/python.exe scripts/phase3_deadlines.py --output data/raw/phase3-deadlines-reproduction.json
```

The first two commands use saved observations and run no games. `python -m pytest tests/test_phase3_deadlines.py` runs the independent constructed-state checks without saved replays. `build(source=None)` also accepts another original candidate source for separately measured interaction experiments; its default build remains byte-identical to the frozen candidate. Diagnosis measurements are `reports/results/phase3-deadline-diagnosis.json`; complete candidate seed-2009 replays are under `reports/replays/phase3-deadlines`. The frozen source snapshot is stored under `reports/sources/<candidate-sha256>.py.gz`. No deployed policy was modified.
