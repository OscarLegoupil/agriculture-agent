"""Test herd capacity on the frozen deadline-policy incumbent."""

import argparse
import gzip
import hashlib
from pathlib import Path

from strategy_screen import screen

INCUMBENT = "64fe323936dc9494add413eb956b0294658a88efe28572332c94676c68a09325"


def frozen_source():
    content = gzip.decompress((Path("reports/sources") / (INCUMBENT + ".py.gz")).read_bytes())
    assert hashlib.sha256(content).hexdigest() == INCUMBENT
    return content.decode("utf-8")


def build(capacity):
    source = frozen_source()
    for old, new in (
        ("desired = dict.fromkeys(ANIMALS, 18)", f"desired = dict.fromkeys(ANIMALS, {capacity})"),
        (
            "len(animals) + sum(stock[a] for a in ANIMALS) < 18",
            f"len(animals) + sum(stock[a] for a in ANIMALS) < {capacity}",
        ),
    ):
        assert source.count(old) == 1
        source = source.replace(old, new)
    compile(source, "capacity", "exec")
    return source


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--capacities", nargs="+", type=int, default=[14, 16, 20])
    parser.add_argument("--seeds", nargs="+", type=int, default=[3000, 3017, 3042, 3063])
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--output", type=Path, default=Path("data/raw/phase4-capacity.json"))
    args = parser.parse_args()
    screen(
        {f"herd{capacity}": build(capacity) for capacity in args.capacities},
        [f"data/raw/reference-{name}/main.py" for name in ("seyam", "cok")],
        args.seeds,
        args.output,
        args.workers,
        inputs=[__file__],
    )


if __name__ == "__main__":
    main()
