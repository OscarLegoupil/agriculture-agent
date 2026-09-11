"""Screen storage-aware retention of products quoted at the verified dollar floor."""

import argparse
import gzip
import hashlib
from pathlib import Path

INCUMBENT = "64fe323936dc9494add413eb956b0294658a88efe28572332c94676c68a09325"


def build():
    """Hold non-fertilizer stock at $1 while there is delivery headroom.

    Official sales at the price floor remove the unit for one dollar and do
    not replenish public market inventory.  Shed products do not decay, so a
    floor sale has no price-recovery benefit.  Preserve fifteen slots for
    incoming worker cargo and use the incumbent's normal sales at day 28/29
    or under storage pressure.
    """
    raw = gzip.decompress((Path("reports/sources") / f"{INCUMBENT}.py.gz").read_bytes())
    assert hashlib.sha256(raw).hexdigest() == INCUMBENT
    source = raw.decode()
    old = """        if sum(shed.values()) < 70 and day < 29:
            quantity = min(quantity, p["sell_batch"])
        if quantity:
            market.append(["SELL", item, quantity])"""
    new = """        if sum(shed.values()) < 70 and day < 29:
            quantity = min(quantity, p["sell_batch"])
        # A $1 sale removes durable shed stock without reducing future supply.
        # Keep room for incoming cargo; final liquidation remains unchanged.
        if (
            item != "FERTILIZER"
            and prices[item] <= 1
            and day < 28
            and sum(shed.values()) < 85
        ):
            quantity = 0
        if quantity:
            market.append(["SELL", item, quantity])"""
    assert source.count(old) == 1
    source = source.replace(old, new)
    compile(source, "floor_holdback", "exec")
    return source


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--screen", action="store_true")
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--output", type=Path, default=Path("data/raw/phase4-floor-holdback.json"))
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
        {"floor_holdback": source},
        [f"data/raw/reference-{name}/main.py" for name in ("seyam", "cok")],
        [3000, 3017, 3042, 3063],
        args.output,
        args.workers,
        inputs=[__file__],
        replays="reports/replays/phase4-floor-holdback",
    )


if __name__ == "__main__":
    main()
