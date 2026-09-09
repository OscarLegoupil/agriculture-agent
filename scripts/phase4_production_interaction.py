"""Use additional crop capacity for grown feed instead of berry-only expansion."""

import argparse
from pathlib import Path

try:
    from .phase4_feed_mix import build as feed_mix
    from .phase4_land import build as land
except ImportError:
    from phase4_feed_mix import build as feed_mix
    from phase4_land import build as land


def build(ratio):
    return feed_mix(ratio, source=land("crop70"))


def main():
    from strategy_screen import screen

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument(
        "--output", type=Path, default=Path("data/raw/phase4-production-interaction.json")
    )
    args = parser.parse_args()
    screen(
        {"expanded_balanced_feed": build(1.0), "expanded_high_feed": build(1.5)},
        [f"data/raw/reference-{name}/main.py" for name in ("seyam", "cok")],
        [3000, 3017, 3042, 3063],
        args.output,
        args.workers,
        inputs=[__file__, "scripts/phase4_land.py", "scripts/phase4_feed_mix.py"],
    )


if __name__ == "__main__":
    main()
