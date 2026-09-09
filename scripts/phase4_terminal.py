"""Audit late animal maintenance against the official production calendar.

Saved observations are offline diagnostics, not policy inputs. No games are run.
"""

import argparse
import gzip
import hashlib
import json
from collections import Counter
from copy import deepcopy
from pathlib import Path


def production_days(tile, animals, after):
    data = animals[tile["animal"]]
    first = tile["placed_day"] + data["first_yield_day"]
    return [
        day for day in range(max(first, after + 1), 30) if (day - first) % data["interval"] == 0
    ]


def audit(path):
    from kaggle_environments.envs.kaggriculture import kaggriculture as game

    replay = json.loads(path.read_bytes())
    seat = int(path.stem.rsplit("-", 1)[1])
    rows = []
    counts = Counter()
    for previous, following in zip(replay["steps"][:-1], replay["steps"][1:], strict=True):
        obs = previous[seat]["observation"]
        day = obs["day"]
        if day < 24:
            continue
        farm = deepcopy(obs["farms"][seat])
        private = deepcopy(obs["private"])
        action = following[seat]["action"] or {}
        for unit, work in enumerate([action.get("farmer", ["PASS"]), *action.get("hands", [])]):
            pos = game._farmer_position(farm, unit)
            before = deepcopy(farm["tiles"][pos[1]][pos[0]]) if pos else None
            game._apply_unit_action(farm, private, unit, work, len(farm["tiles"]), day, 24)
            if (
                not work
                or work[0] not in ("FEED", "CARE")
                or not isinstance(before, dict)
                or "animal" not in before
            ):
                continue
            after = farm["tiles"][pos[1]][pos[0]]
            field = "fed_today" if work[0] == "FEED" else "cared_today"
            if before[field] or not after[field]:
                continue
            events = production_days(before, game.ANIMALS, day)
            # EOD produces before today's care enters the pending accumulator.
            care_events = [event for event in events if event > day + 1]
            useless_care = work[0] == "CARE" and not care_events
            no_primary_feed = work[0] == "FEED" and not events and not before["yield_units"]
            counts[work[0]] += 1
            counts["care_without_deliverable_bonus"] += int(useless_care)
            counts["feed_without_future_primary_or_held"] += int(no_primary_feed)
            counts["feed_no_future_primary_but_held"] += int(
                work[0] == "FEED" and not events and bool(before["yield_units"])
            )
            counts["feed_on_terminal_day"] += int(work[0] == "FEED" and day == 29)
            if no_primary_feed:
                counts["feed_current_quote_upper_saving"] += obs["market"]["prices"]["WHEAT"]
            if useless_care or no_primary_feed:
                rows.append(
                    dict(
                        day=day,
                        hour=obs["hour"],
                        unit=unit,
                        work=work[0],
                        animal=before["animal"],
                        placed_day=before["placed_day"],
                        held=before["yield_units"],
                        unfed=before["consecutive_unfed"],
                        future_primary=events,
                        future_care=care_events,
                    )
                )
    return {
        "replay": str(path),
        "replay_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "seat": seat,
        "counts": dict(counts),
        "actions": rows,
    }


def check():
    from kaggle_environments.envs.kaggriculture import kaggriculture as game

    checks = []
    for animal, data in game.ANIMALS.items():
        for production in (28, 29, 30):
            tile = dict(
                animal=animal,
                placed_day=production - data["first_yield_day"],
                fed_today=True,
                cared_today=True,
                consecutive_unfed=0,
                yield_units=0,
                pending_care_bonus=2,
                fertilizer_available=False,
            )
            farm = {"tiles": [[deepcopy(tile)]]}
            game._daily_refresh_animals(farm, production - 1)
            after = farm["tiles"][0][0]
            assert after["yield_units"] == 3
            assert after["pending_care_bonus"] == 1
            events = production_days(tile, game.ANIMALS, production - 1)
            assert (events[0] if events else None) == (production if production < 30 else None)
            checks.append(
                {
                    "animal": animal,
                    "production_day": production,
                    "held_after": after["yield_units"],
                    "pending_after": 1,
                }
            )
    # Stored primary product disappears with an escape; a calendar-only removal
    # of maintenance is unsafe when that product still needs harvesting.
    for fed in (False, True):
        tile = dict(
            animal="SHEEP",
            placed_day=0,
            fed_today=fed,
            cared_today=False,
            consecutive_unfed=1,
            yield_units=4,
            pending_care_bonus=0,
            fertilizer_available=False,
        )
        farm = {"tiles": [[tile]]}
        game._daily_refresh_animals(farm, 28)
        after = farm["tiles"][0][0]
        assert ("animal" in after) == fed
        if fed:
            assert after["yield_units"] == 4
    return checks


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path("data/raw/phase4-terminal-audit.json"))
    args = parser.parse_args()
    report = {
        "official_probes": check(),
        "replays": [
            audit(path) for path in sorted(Path("reports/replays/phase4-losses").glob("*.json"))
        ],
    }
    from kaggle_environments.envs.kaggriculture import kaggriculture as game

    report["artifact_sha256"] = "64fe323936dc9494add413eb956b0294658a88efe28572332c94676c68a09325"
    report["interpreter_sha256"] = hashlib.sha256(Path(game.__file__).read_bytes()).hexdigest()
    report["scope"] = "Offline action reconstruction on four existing loss replays; zero new games"
    args.output.parent.mkdir(parents=True, exist_ok=True)
    raw = (json.dumps(report, indent=2) + "\n").encode()
    args.output.write_bytes(gzip.compress(raw, mtime=0) if args.output.suffix == ".gz" else raw)
    print(json.dumps([row["counts"] for row in report["replays"]], indent=2))


if __name__ == "__main__":
    main()
