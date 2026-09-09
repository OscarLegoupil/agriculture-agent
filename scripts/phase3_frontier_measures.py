"""Extract action-order and input-logistics evidence from saved audit replays.

No games run here. Requested actions are located against their actual preceding
observations; counts do not imply that every requested operation succeeded.
"""

import argparse
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path


def measure_seat(steps, seat):
    operations = defaultdict(list)
    pickups = defaultdict(Counter)
    input_drops, placements = Counter(), Counter()
    fertilizer_buys = 0
    opening = []
    for index in range(1, len(steps)):
        observation = steps[index - 1][seat]["observation"]
        farm = observation["farms"][seat]
        action = steps[index][seat].get("action") or {}
        positions = [farm["farmer"], *farm["hands"]]
        inventories = observation["private"]["inventories"]
        work = [action.get("farmer", ["PASS"]), *action.get("hands", [])]
        for worker, (position, operation) in enumerate(zip(positions, work, strict=False)):
            if not operation:
                continue
            x, y = position
            tile = farm["tiles"][y][x]
            if (
                isinstance(tile, dict)
                and tile.get("kind") == "PLANT"
                and operation[0] in ("WATER", "FERTILIZE")
            ):
                operations[observation["day"], x, y, tile["crop"]].append(operation[0])
            if operation[0] == "PICKUP":
                pickups[operation[1]][operation[2] if len(operation) > 2 else 1] += 1
            if operation[0] == "PLACE":
                placements[operation[1]] += 1
            if operation[0] == "DROP":
                for item in ("WHEAT", "FERTILIZER"):
                    input_drops[item] += inventories[worker].get(item, 0)
        fertilizer_buys += sum(
            order[2]
            for order in action.get("market", [])
            if order[:2] == ["BUY_PRODUCT", "FERTILIZER"]
        )
        if index in (25, 73, 121, 241, 361):
            counts = Counter(
                tile.get("crop", tile.get("animal", tile.get("kind")))
                for row in farm["tiles"]
                for tile in row
                if isinstance(tile, dict)
            )
            opening.append((index - 1, farm["money"], dict(counts)))
    annual = [
        sequence
        for key, sequence in operations.items()
        if key[-1] in ("WHEAT", "MELON", "CARROT") and "FERTILIZE" in sequence
    ]
    return {
        "fertilized_oneshot_days": len(annual),
        "water_before_fertilizer": sum(
            "WATER" in sequence and sequence.index("WATER") < sequence.index("FERTILIZE")
            for sequence in annual
        ),
        "pickups": {item: dict(counts) for item, counts in pickups.items()},
        "input_dropped": dict(input_drops),
        "place": dict(placements),
        "fertilizer_bought": fertilizer_buys,
        "opening": opening,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--replays", type=Path, default=Path("reports/replays/phase2-validation"))
    parser.add_argument(
        "--output", type=Path, default=Path("reports/results/phase3-frontier-measures.json")
    )
    args = parser.parse_args()
    results = {}
    for opponent in ("cok", "seyam"):
        matches = sorted(args.replays.glob(f"0098*-reference-{opponent}-main-2000-0.json"))
        if len(matches) != 1:
            raise ValueError(f"Expected one pinned {opponent} replay, found {len(matches)}")
        path = matches[0]
        content = path.read_bytes()
        replay = json.loads(content.decode("utf-8"))
        results[opponent] = {
            "replay": path.as_posix(),
            "replay_sha256": hashlib.sha256(content).hexdigest(),
            "seats": {seat: measure_seat(replay["steps"], seat) for seat in (0, 1)},
        }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(
            {
                "measurement": "Located requested actions and observed stock; not a successful-action ledger",
                "opponents": results,
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    print(args.output)


if __name__ == "__main__":
    main()
