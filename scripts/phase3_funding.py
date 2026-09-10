"""Test feasible deadlines and earlier crop-funded flexible herd expansion."""

import argparse
from pathlib import Path

from phase2_logistics import replace
from phase3_deadlines import build as deadlines
from phase3_interactions import build as combined
from strategy_screen import screen


def build(name):
    assert name in ("deadline", "deadline_net", "funded_open", "funded_growth")
    source = deadlines(combined("mixed_capacity"))
    if name in ("funded_open", "funded_growth"):
        source = replace(
            source,
            "    if day < 8:\n        desired = dict(COW=2, SHEEP=2, GOOSE=0)",
            '    if day < 8 and (day < 3 or crops["MELON"] < 12):\n        desired = dict(COW=2, SHEEP=2, GOOSE=0)',
        )
    if name == "funded_growth":
        source = replace(
            source,
            'cash > cost + max(150, feed_need * prices["WHEAT"])',
            'cash > cost + max(150, feed_need * prices["WHEAT"] + (500 if day < 8 else 0))',
        )
    if name == "deadline_net":
        source = replace(
            source, "options.append((net / cost, animal))", "options.append((net, animal))"
        )
    compile(source, name, "exec")
    return source


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--names", nargs="+", default=["deadline", "funded_open", "funded_growth"])
    parser.add_argument("--seeds", nargs="+", type=int, default=[2000, 2003, 2009, 2013])
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--output", type=Path, default=Path("data/raw/phase3-funding.json"))
    args = parser.parse_args()
    screen(
        {name: build(name) for name in args.names},
        [f"data/raw/reference-{name}/main.py" for name in ("seyam", "cok")],
        args.seeds,
        args.output,
        args.workers,
        inputs=[__file__, "scripts/phase3_deadlines.py", "scripts/phase3_interactions.py"],
    )


if __name__ == "__main__":
    main()
