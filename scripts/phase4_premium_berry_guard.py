"""Avoid forcing feed wheat while strawberries trade at an observed premium."""

import argparse
import gzip
import hashlib
from pathlib import Path

try:
    from .phase4_feed_mix import INCUMBENT
except ImportError:
    from phase4_feed_mix import INCUMBENT


def build():
    """Keep the high-feed plan except at a 49% public strawberry premium.

    The 1.5 wheat target is the frozen high-feed policy. At a strawberry quote
    of at least 1.49 times its base price, it no longer overrides the normal
    finite-season ranking. This guards the explicit crop-displacement decision;
    all market, cash, seed and crop-value calculations stay unchanged.
    """
    raw = gzip.decompress((Path("reports/sources") / f"{INCUMBENT}.py.gz").read_bytes())
    assert hashlib.sha256(raw).hexdigest() == INCUMBENT
    source = raw.decode()
    needle = "        crop = max(values, key=lambda c: values[c])"
    assert source.count(needle) == 1
    replacement = f"""        # Do not displace a premium berry cohort with feed wheat.
        berry_premium = prices["STRAWBERRY"] >= BASE["STRAWBERRY"] * 1.49
        if 8 <= day <= 24 and animals and not berry_premium:
            target_wheat = min(28, max(7, math.ceil(len(animals) * 1.5)))
            feed_value = crop_value("WHEAT", day, forecast["WHEAT"], fert_price, False)
            if planned["WHEAT"] < target_wheat and feed_value > 0:
                values["WHEAT"] = max(values.values()) + 1
{needle}"""
    source = source.replace(needle, replacement)
    compile(source, "premium_berry_guard", "exec")
    return source


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--screen", action="store_true")
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument(
        "--output", type=Path, default=Path("data/raw/phase4-premium-berry-guard.json")
    )
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
        {"premium_berry_guard": source},
        [f"data/raw/reference-{name}/main.py" for name in ("seyam", "cok")],
        [3000, 3017, 3042, 3063],
        args.output,
        args.workers,
        inputs=[__file__],
        replays="reports/replays/phase4-premium-berry-guard",
    )


if __name__ == "__main__":
    main()
