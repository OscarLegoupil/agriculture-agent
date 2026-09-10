"""Screen a public Yarn Store guard against cow-heavy herd concentration."""

import argparse
import gzip
import hashlib
from pathlib import Path

INCUMBENT = "64fe323936dc9494add413eb956b0294658a88efe28572332c94676c68a09325"


def build():
    """Limit cows to eight only after an observable single-product wool demand.

    The shared herd ceiling and existing economic ranking remain responsible
    for all other species choices.  This prevents a mature milk concentration
    from consuming every remaining animal slot after a Yarn Store is already
    known, while preserving the incumbent before that public demand signal.
    """
    raw = gzip.decompress((Path("reports/sources") / f"{INCUMBENT}.py.gz").read_bytes())
    assert hashlib.sha256(raw).hexdigest() == INCUMBENT
    source = raw.decode()
    old = '''    desired = dict.fromkeys(ANIMALS, 18)
    if day < 8:'''
    new = '''    desired = dict.fromkeys(ANIMALS, 18)
    # A known single-product wool buyer diversifies the shared herd budget.
    if "YARN_STORE" in obs["town"]["unlocked_shops"]:
        desired["COW"] = 8
    if day < 8:'''
    assert source.count(old) == 1
    source = source.replace(old, new)
    compile(source, "yarn_herd", "exec")
    return source


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--screen", action="store_true")
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--output", type=Path, default=Path("data/raw/phase4-yarn-herd.json"))
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
        {"yarn_store_herd": source},
        [f"data/raw/reference-{name}/main.py" for name in ("seyam", "cok")],
        [3000, 3017, 3042, 3063],
        args.output,
        args.workers,
        inputs=[__file__],
        replays="reports/replays/phase4-yarn-herd",
    )


if __name__ == "__main__":
    main()
