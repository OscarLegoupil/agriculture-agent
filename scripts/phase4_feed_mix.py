"""Test sustained grown-feed cohorts on the corrected annual-crop controller."""

import argparse
import contextlib
import gzip
import hashlib
import io
import json
from pathlib import Path

INCUMBENT = "64fe323936dc9494add413eb956b0294658a88efe28572332c94676c68a09325"


def build(ratio, source=None):
    if source is None:
        raw = gzip.decompress((Path("reports/sources") / f"{INCUMBENT}.py.gz").read_bytes())
        assert hashlib.sha256(raw).hexdigest() == INCUMBENT
        source = raw.decode()
    before = "        crop = max(values, key=lambda c: values[c])"
    assert source.count(before) == 1
    replacement = f"""        # This experimental cohort target tests purchased versus grown feed.
        # Preserve the opening; leave five days for maturation and delivery.
        if 8 <= day <= 24 and animals:
            target_wheat = min(28, max(7, math.ceil(len(animals) * {ratio!r})))
            feed_value = crop_value("WHEAT", day, forecast["WHEAT"], fert_price, False)
            if planned["WHEAT"] < target_wheat and feed_value > 0:
                values["WHEAT"] = max(values.values()) + 1
{before}"""
    source = source.replace(before, replacement)
    compile(source, "feed_mix", "exec")
    return source


def verify_parity():
    raw = gzip.decompress((Path("reports/sources") / f"{INCUMBENT}.py.gz").read_bytes())
    baseline = {}
    exec(raw, baseline)
    path = next(Path("reports/replays/phase4-losses").glob("*3029-0.json"))
    replay = json.loads(path.read_bytes())
    result = {
        "kind": "unchanged-opening-and-terminal saved-action parity",
        "incumbent": INCUMBENT,
        "replay": str(path),
        "replay_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "candidates": [],
    }
    for ratio in (1.0, 1.5):
        source = build(ratio).encode()
        digest = hashlib.sha256(source).hexdigest()
        namespace = {}
        exec(source, namespace)
        compared = 0
        for step in replay["steps"]:
            obs = step[0]["observation"]
            if obs["day"] not in (0, 3, 7, 25, 28, 29) or obs["hour"] not in (0, 6, 12, 18, 22):
                continue
            stderr = io.StringIO()
            with contextlib.redirect_stderr(stderr):
                assert baseline["agent"](obs, replay["configuration"]) == namespace["agent"](
                    obs, replay["configuration"]
                )
            assert not stderr.getvalue()
            compared += 1
        (Path("reports/sources") / f"{digest}.py.gz").write_bytes(gzip.compress(source, mtime=0))
        result["candidates"].append({"ratio": ratio, "sha256": digest, "equal_actions": compared})
    Path("reports/results/phase4-feed-mix-parity.json").write_text(
        json.dumps(result, indent=2) + "\n", encoding="utf-8"
    )


def main():

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--output", type=Path, default=Path("data/raw/phase4-feed-mix.json"))
    parser.add_argument("--verify-parity", action="store_true")
    args = parser.parse_args()
    if args.verify_parity:
        verify_parity()
        return
    from strategy_screen import screen

    screen(
        {"balanced_feed": build(1.0), "self_feed": build(1.5)},
        [f"data/raw/reference-{name}/main.py" for name in ("seyam", "cok")],
        [3000, 3017, 3042, 3063],
        args.output,
        args.workers,
        inputs=[__file__],
    )


if __name__ == "__main__":
    main()
