"""Screen feed production when the public rival herd is materially cow-heavy."""

import argparse
import gzip
import hashlib
from pathlib import Path

try:
    from .phase4_feed_mix import INCUMBENT
except ImportError:
    from phase4_feed_mix import INCUMBENT


def build():
    """Apply the frozen wheat target only to an observable production shape."""
    raw = gzip.decompress((Path("reports/sources") / f"{INCUMBENT}.py.gz").read_bytes())
    assert hashlib.sha256(raw).hexdigest() == INCUMBENT
    source = raw.decode()
    needle = "        crop = max(values, key=lambda c: values[c])"
    assert source.count(needle) == 1
    replacement = f'''        rival = obs["farms"][1 - obs["player"]]
        rival_animals = [
            tile["animal"]
            for row in rival["tiles"]
            for tile in row
            if isinstance(tile, dict) and "animal" in tile
        ]
        rival_cows = rival_animals.count("COW")
        rival_sheep = rival_animals.count("SHEEP")
        # A visible cow-heavy rival is a public milk/fertilizer supply signal.
        cow_heavy_rival = rival_cows >= 6 and rival_cows >= rival_sheep + 2
        if 8 <= day <= 24 and animals and cow_heavy_rival:
            target_wheat = min(28, max(7, math.ceil(len(animals) * 1.5)))
            feed_value = crop_value("WHEAT", day, forecast["WHEAT"], fert_price, False)
            if planned["WHEAT"] < target_wheat and feed_value > 0:
                values["WHEAT"] = max(values.values()) + 1
{needle}'''
    source = source.replace(needle, replacement)
    compile(source, "rival_shape_feed", "exec")
    return source


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--screen", action="store_true")
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--output", type=Path, default=Path("data/raw/phase4-rival-shape-feed.json"))
    args = parser.parse_args()
    source = build()
    digest = hashlib.sha256(source.encode()).hexdigest()
    print(digest)
    if not args.screen:
        return
    assert 1 <= args.workers <= 4
    assert not args.output.exists(), "Do not overwrite an existing experiment"
    from strategy_screen import screen

    screen(
        {"cow_heavy_rival_feed": source},
        [f"data/raw/reference-{name}/main.py" for name in ("seyam", "cok")],
        [3000, 3017, 3042, 3063],
        args.output,
        args.workers,
        inputs=[__file__],
        replays="reports/replays/phase4-rival-shape-feed",
    )


if __name__ == "__main__":
    main()
