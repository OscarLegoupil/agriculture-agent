"""Test whether the initial in-flight animal queue preserves sheep startup care."""

import argparse
import gzip
import hashlib
from pathlib import Path

INCUMBENT = "64fe323936dc9494add413eb956b0294658a88efe28572332c94676c68a09325"


def build():
    """Allow the existing two-cow/two-sheep opening to enter the queue on day zero.

    The desired caps, economics, sites, worker hiring, feed accounting and all
    later investment gates remain unchanged. This changes the purchase queue,
    not the number of opening animals.
    """
    raw = gzip.decompress((Path("reports/sources") / f"{INCUMBENT}.py.gz").read_bytes())
    assert hashlib.sha256(raw).hexdigest() == INCUMBENT
    source = raw.decode()
    old = "        and sum(stock[a] for a in ANIMALS) < 2\n"
    new = "        and sum(stock[a] for a in ANIMALS) < (4 if day == 0 else 2)\n"
    assert source.count(old) == 1
    source = source.replace(old, new)
    compile(source, "opening_queue", "exec")
    return source


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--screen", action="store_true")
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--output", type=Path, default=Path("data/raw/phase4-opening-queue.json"))
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
        {"opening_queue": source},
        [f"data/raw/reference-{name}/main.py" for name in ("seyam", "cok")],
        [3000, 3017, 3042, 3063],
        args.output,
        args.workers,
        inputs=[__file__],
        replays="reports/replays/phase4-opening-queue",
    )


if __name__ == "__main__":
    main()
