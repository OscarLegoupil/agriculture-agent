"""Screen feed pickups sized to an observable local cluster of unfed animals."""

import argparse
import gzip
import hashlib
from pathlib import Path

INCUMBENT = "64fe323936dc9494add413eb956b0294658a88efe28572332c94676c68a09325"


def build():
    """Retain three-unit default pickup and expand only for a local feed circuit."""
    raw = gzip.decompress((Path("reports/sources") / f"{INCUMBENT}.py.gz").read_bytes())
    assert hashlib.sha256(raw).hexdigest() == INCUMBENT
    source = raw.decode()
    old = '''                amount = min(
                    shed[required], 3 if required == "WHEAT" else 4, demand_inputs[required]
                )'''
    new = '''                nearby_feed = sum(
                    other_op == "FEED" and distance(other_target, target) <= 3
                    for other_target, other_op, _, _, _ in tasks
                )
                batch_size = (
                    min(6, max(3, nearby_feed)) if required == "WHEAT" else 4
                )
                amount = min(shed[required], batch_size, demand_inputs[required])'''
    assert source.count(old) == 1
    source = source.replace(old, new)
    compile(source, "local_feed_batch", "exec")
    return source


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--screen", action="store_true")
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--output", type=Path, default=Path("data/raw/phase4-local-feed-batch.json"))
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
        {"local_feed_batch": source},
        [f"data/raw/reference-{name}/main.py" for name in ("seyam", "cok")],
        [3000, 3017, 3042, 3063],
        args.output,
        args.workers,
        inputs=[__file__],
        replays="reports/replays/phase4-local-feed-batch",
    )


if __name__ == "__main__":
    main()
