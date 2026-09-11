"""Screen declared structural candidates on eight new development seed clusters."""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from experiments.season_plans import build
from strategy_screen import screen


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument(
        "--candidates", nargs="+", default=["incumbent", "wool", "dairy", "balanced"]
    )
    parser.add_argument("--seeds", nargs="+", type=int, default=list(range(5000, 5008)))
    parser.add_argument("--opponents", nargs="+", default=["cok", "seyam"])
    args = parser.parse_args()
    candidates = {}
    for name in args.candidates:
        if name == "incumbent":
            candidates[name] = Path("submissions/20260909-v8/main.py").read_text(encoding="utf-8")
        elif name == "market":
            from experiments.market_dispatch import build as market_build

            candidates[name] = market_build()
        elif name == "routes":
            from experiments.service_routes import build as routes_build

            candidates[name] = routes_build()
        elif name == "terminal":
            from experiments.terminal_crops import build as terminal_build

            candidates[name] = terminal_build()
        elif name.endswith("_herd"):
            candidates[name] = build(name.removesuffix("_herd"), scope="herd")
        else:
            candidates[name] = build(name)
    screen(
        candidates,
        [f"data/raw/reference-{name}/main.py" for name in args.opponents],
        args.seeds,
        args.output,
        args.workers,
        inputs=[__file__, *map(str, Path("experiments").glob("*.py"))],
        replays="reports/replays/breakthrough",
    )


if __name__ == "__main__":
    main()
