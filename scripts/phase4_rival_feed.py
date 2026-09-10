"""Grow more wheat when visible rival livestock creates a feed-demand imbalance."""

import argparse
import gzip
import hashlib
import json
from copy import deepcopy
from pathlib import Path

try:
    from .phase4_feed_mix import INCUMBENT
except ImportError:
    from phase4_feed_mix import INCUMBENT


def build():
    """Use a public five-animal rival feed-demand lead as the admission signal.

    Every animal consumes wheat. The rule activates the previously measured
    1.5-wheat-per-own-animal target only while the rival visibly has at least
    five more animals. It preserves the incumbent's crop valuation, seed/cash
    gates and all opening behavior.
    """
    raw = gzip.decompress((Path("reports/sources") / f"{INCUMBENT}.py.gz").read_bytes())
    assert hashlib.sha256(raw).hexdigest() == INCUMBENT
    source = raw.decode()
    needle = "        crop = max(values, key=lambda c: values[c])"
    assert source.count(needle) == 1
    replacement = f"""        rival_animals = sum(
            1
            for row in obs["farms"][1 - obs["player"]]["tiles"]
            for tile in row
            if isinstance(tile, dict) and "animal" in tile
        )
        # Rival livestock is public and represents ongoing wheat demand.
        if 8 <= day <= 24 and rival_animals >= len(animals) + 5:
            target_wheat = min(28, max(7, math.ceil(len(animals) * 1.5)))
            feed_value = crop_value("WHEAT", day, forecast["WHEAT"], fert_price, False)
            if planned["WHEAT"] < target_wheat and feed_value > 0:
                values["WHEAT"] = max(values.values()) + 1
{needle}"""
    source = source.replace(needle, replacement)
    compile(source, "rival_feed", "exec")
    return source


def diagnose(output):
    """Count public activation states and action changes on saved replays only."""
    baseline, candidate = {}, {}
    raw = gzip.decompress((Path("reports/sources") / f"{INCUMBENT}.py.gz").read_bytes())
    exec(raw, baseline)
    source = build()
    exec(source, candidate)
    records = []
    activations = 0
    for path in sorted(Path("reports/replays/phase4-high-feed-field").glob("*.json")):
        replay = json.loads(path.read_bytes())
        for index, step in enumerate(replay["steps"]):
            for seat in (0, 1):
                obs = deepcopy(step[seat]["observation"])
                obs.setdefault("step", index)
                obs["player"] = seat
                if not 8 <= obs["day"] <= 24:
                    continue
                own = sum(
                    1
                    for row in obs["farms"][seat]["tiles"]
                    for tile in row
                    if isinstance(tile, dict) and "animal" in tile
                )
                rival = sum(
                    1
                    for row in obs["farms"][1 - seat]["tiles"]
                    for tile in row
                    if isinstance(tile, dict) and "animal" in tile
                )
                active = rival >= own + 5
                activations += active
                before = baseline["agent"](deepcopy(obs), replay["configuration"])
                after = candidate["agent"](deepcopy(obs), replay["configuration"])
                if before != after and len(records) < 80:
                    records.append(
                        {
                            "replay": path.name,
                            "seat": seat,
                            "day": obs["day"],
                            "hour": obs["hour"],
                            "own_animals": own,
                            "rival_animals": rival,
                            "active": active,
                            "baseline_market": before["market"],
                            "candidate_market": after["market"],
                        }
                    )
    result = {
        "complete": True,
        "kind": "saved-observation public-rival-demand sensitivity; no games",
        "incumbent_sha256": INCUMBENT,
        "candidate_sha256": hashlib.sha256(source.encode()).hexdigest(),
        "active_observations": activations,
        "changed_action_examples": records,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--diagnose", action="store_true")
    parser.add_argument("--screen", action="store_true")
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument(
        "--output", type=Path, default=Path("reports/results/phase4-rival-feed-diagnosis.json")
    )
    args = parser.parse_args()
    source = build()
    digest = hashlib.sha256(source.encode()).hexdigest()
    print(digest)
    if args.diagnose:
        print(json.dumps(diagnose(args.output), indent=2))
    if args.screen:
        assert 1 <= args.workers <= 4
        assert not args.output.exists(), "Do not overwrite an existing experiment"
        from strategy_screen import screen

        screen(
            {"rival_feed_pressure": source},
            [f"data/raw/reference-{name}/main.py" for name in ("seyam", "cok")],
            [3000, 3017, 3042, 3063],
            args.output,
            args.workers,
            inputs=[__file__],
            replays="reports/replays/phase4-rival-feed",
        )


if __name__ == "__main__":
    main()
