"""Screen larger shared-input batches for local multi-service worker circuits."""

import argparse
import gzip
import hashlib
from pathlib import Path

INCUMBENT = "64fe323936dc9494add413eb956b0294658a88efe28572332c94676c68a09325"


def build():
    """Use legal six-wheat/eight-fertilizer batches with matching reservations."""
    raw = gzip.decompress((Path("reports/sources") / f"{INCUMBENT}.py.gz").read_bytes())
    assert hashlib.sha256(raw).hexdigest() == INCUMBENT
    source = raw.decode()
    old_limit = """                if shed.get(required, 0) <= 0 or fetches[required] >= max(
                    1, math.ceil(demand_inputs[required] / 3)
                ):
                    continue
                cost = home_dist + 2 + distance(home, target)"""
    new_limit = """                batch_size = 6 if required == "WHEAT" else 8
                if shed.get(required, 0) <= 0 or fetches[required] >= max(
                    1, math.ceil(demand_inputs[required] / batch_size)
                ):
                    continue
                cost = home_dist + 2 + distance(home, target)"""
    assert source.count(old_limit) == 1
    source = source.replace(old_limit, new_limit)
    old_amount = """                amount = min(
                    shed[required], 3 if required == "WHEAT" else 4, demand_inputs[required]
                )"""
    new_amount = """                amount = min(
                    shed[required], 6 if required == "WHEAT" else 8, demand_inputs[required]
                )"""
    assert source.count(old_amount) == 1
    source = source.replace(old_amount, new_amount)
    compile(source, "input_batches", "exec")
    return source


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--screen", action="store_true")
    parser.add_argument("--field", action="store_true")
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--output", type=Path, default=Path("data/raw/phase4-input-batches.json"))
    args = parser.parse_args()
    source = build()
    digest = hashlib.sha256(source.encode()).hexdigest()
    print(digest)
    if not (args.screen or args.field):
        return
    assert 1 <= args.workers <= 4
    if args.field and args.output == Path("data/raw/phase4-input-batches.json"):
        args.output = Path("data/raw/phase4-input-batches-field.json")
    assert not args.output.exists(), "Do not overwrite an existing experiment"
    from strategy_screen import screen

    screen(
        {"service_input_batches": source},
        [f"data/raw/reference-{name}/main.py" for name in ("seyam", "cok")],
        list(range(3000, 3032)) if args.field else [3000, 3017, 3042, 3063],
        args.output,
        args.workers,
        inputs=[__file__],
        replays="reports/replays/phase4-input-batches",
    )


if __name__ == "__main__":
    main()
