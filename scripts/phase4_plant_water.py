"""Screen an explicit next-turn watering reservation for newly planted crops."""

import argparse
import gzip
import hashlib
from pathlib import Path

INCUMBENT = "64fe323936dc9494add413eb956b0294658a88efe28572332c94676c68a09325"


def build():
    """Raise only the water task created immediately after a successful plant.

    The observation exposes ``planted_day`` and ``watered_today``.  A crop
    planted earlier in the current day must be watered before refresh or the
    paid seed becomes a weed.  This is a stateless reservation: it does not
    assume which worker planted, retain hidden state, or alter crop choice.
    Existing escape-deadline reservations are made before ordinary matching
    and remain dominant.
    """
    raw = gzip.decompress((Path("reports/sources") / f"{INCUMBENT}.py.gz").read_bytes())
    assert hashlib.sha256(raw).hexdigest() == INCUMBENT
    source = raw.decode()
    old = '''                140
                if water_before_harvest
                else (
                    p["deadline_boost"]'''
    new = '''                260
                if tile["planted_day"] == day and not tile["watered_today"]
                else (
                    140
                    if water_before_harvest
                    else (
                        p["deadline_boost"]'''
    assert source.count(old) == 1
    source = source.replace(old, new)
    old_close = '''                    else 65
                ),
            )'''
    new_close = '''                    else 65
                    )
                ),
            )'''
    assert source.count(old_close) == 1
    source = source.replace(old_close, new_close)
    compile(source, "plant_water", "exec")
    return source


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--screen", action="store_true")
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument(
        "--output", type=Path, default=Path("data/raw/phase4-plant-water.json")
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
        {"plant_water_reservation": source},
        [f"data/raw/reference-{name}/main.py" for name in ("seyam", "cok")],
        [3000, 3017, 3042, 3063],
        args.output,
        args.workers,
        inputs=[__file__],
        replays="reports/replays/phase4-plant-water",
    )


if __name__ == "__main__":
    main()
