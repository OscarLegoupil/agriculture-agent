"""Screen forecast-ranked commercial cohorts in place of forced early berries."""

import argparse
import gzip
import hashlib
from pathlib import Path

INCUMBENT = "64fe323936dc9494add413eb956b0294658a88efe28572332c94676c68a09325"


def build():
    """Retain the wheat/melon opening but stop overriding demand-aware values.

    The incumbent's day-3-to-14 cohort rule always makes strawberries beat
    the already-computed finite-season values.  This candidate leaves opening
    bridge crops unchanged and lets the public-inventory forecast, own planned
    saturation, fertilizer cost and remaining season select commercial crops.
    """
    raw = gzip.decompress((Path("reports/sources") / f"{INCUMBENT}.py.gz").read_bytes())
    assert hashlib.sha256(raw).hexdigest() == INCUMBENT
    source = raw.decode()
    old = """        # Short crops bridge the first long cohort's startup costs.
        # Later recurring cohorts must arrive early enough to repay before liquidation.
        if day < 15:
            cohort_crop = "WHEAT" if planned["WHEAT"] < 7 else "MELON" if day < 3 else "STRAWBERRY"
            current_value = crop_value(
                cohort_crop,
                day,
                prices[cohort_crop],
                fert_price,
                use_fert and CROPS[cohort_crop][3] > 0,
            )
            if current_value > 0:
                values[cohort_crop] = max(1, max(values.values()) + 1)
"""
    new = """        # Keep the opening bridge crops, then respect the forecast-ranked
        # commercial values above rather than forcing one crop through day 14.
        if day < 3:
            cohort_crop = "WHEAT" if planned["WHEAT"] < 7 else "MELON"
            current_value = crop_value(
                cohort_crop,
                day,
                prices[cohort_crop],
                fert_price,
                use_fert and CROPS[cohort_crop][3] > 0,
            )
            if current_value > 0:
                values[cohort_crop] = max(1, max(values.values()) + 1)
"""
    assert source.count(old) == 1
    source = source.replace(old, new)
    compile(source, "demand_cohort", "exec")
    return source


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--screen", action="store_true")
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--output", type=Path, default=Path("data/raw/phase4-demand-cohort.json"))
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
        {"demand_ranked_cohort": source},
        [f"data/raw/reference-{name}/main.py" for name in ("seyam", "cok")],
        [3000, 3017, 3042, 3063],
        args.output,
        args.workers,
        inputs=[__file__],
        replays="reports/replays/phase4-demand-cohort",
    )


if __name__ == "__main__":
    main()
