"""Screen a funded early sheep allocation after a public Yarn Store unlock."""

import argparse
import gzip
import hashlib
from pathlib import Path

INCUMBENT = "64fe323936dc9494add413eb956b0294658a88efe28572332c94676c68a09325"


def build():
    """Release the opening herd gate only for observed wool demand from day 3.

    The candidate retains the two-cow/two-sheep opening everywhere else.  On a
    known Yarn Store, it permits a modest four-cow/eight-sheep allocation under
    the incumbent's cash, feed, travel, total-herd and economic-return gates.
    It cannot admit geese or an unlimited herd before day 8.
    """
    raw = gzip.decompress((Path("reports/sources") / f"{INCUMBENT}.py.gz").read_bytes())
    assert hashlib.sha256(raw).hexdigest() == INCUMBENT
    source = raw.decode()
    old = """    if day < 8:
        desired = dict(COW=2, SHEEP=2, GOOSE=0)
    purchase = None"""
    new = """    if day < 8:
        desired = dict(COW=2, SHEEP=2, GOOSE=0)
        if day >= 3 and "YARN_STORE" in obs["town"]["unlocked_shops"]:
            desired = dict(COW=4, SHEEP=8, GOOSE=0)
    purchase = None"""
    assert source.count(old) == 1
    source = source.replace(old, new)
    compile(source, "yarn_opening", "exec")
    return source


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--screen", action="store_true")
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--output", type=Path, default=Path("data/raw/phase4-yarn-opening.json"))
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
        {"yarn_store_opening": source},
        [f"data/raw/reference-{name}/main.py" for name in ("seyam", "cok")],
        [3000, 3017, 3042, 3063],
        args.output,
        args.workers,
        inputs=[__file__],
        replays="reports/replays/phase4-yarn-opening",
    )


if __name__ == "__main__":
    main()
