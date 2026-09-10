"""Make the grown-feed cohort conditional on observable wheat-versus-berry value."""

import argparse
import gzip
import hashlib
import json
from copy import deepcopy
from pathlib import Path

try:
    from .phase4_feed_mix import INCUMBENT
except ImportError:
    from phase4_feed_mix import INCUMBENT


def build(ratio=1.5):
    """Retain the feed target only where the unforced wheat value beats berries.

    ``values`` already includes current market observations, forecasted public
    supply, own planned-crop saturation, seed cost and the existing fertilizer
    eligibility rule. The comparison occurs after the startup cohort rule so it
    can decline an otherwise forced berry when wheat's observable value wins.
    """
    raw = gzip.decompress((Path("reports/sources") / f"{INCUMBENT}.py.gz").read_bytes())
    assert hashlib.sha256(raw).hexdigest() == INCUMBENT
    source = raw.decode()
    needle = "        crop = max(values, key=lambda c: values[c])"
    assert source.count(needle) == 1
    replacement = f"""        # A feed target is useful only when it beats the displaced berry cohort.
        # Both values are from this observation's unforced finite-season model.
        unforced_wheat = values["WHEAT"]
        unforced_berries = values["STRAWBERRY"]
        if 8 <= day <= 24 and animals:
            target_wheat = min(28, max(7, math.ceil(len(animals) * {ratio!r})))
            if planned["WHEAT"] < target_wheat and unforced_wheat > unforced_berries > 0:
                values["WHEAT"] = max(values.values()) + 1
{needle}"""
    source = source.replace(needle, replacement)
    compile(source, "adaptive_feed", "exec")
    return source


def diagnose(output):
    """Compare legal actions on saved COK loss observations without new games."""
    baseline = {}
    adaptive = {}
    raw = gzip.decompress((Path("reports/sources") / f"{INCUMBENT}.py.gz").read_bytes())
    exec(raw, baseline)
    source = build()
    exec(source, adaptive)
    records = []
    for path in sorted(Path("reports/replays/phase4-losses").glob("*.json")):
        replay = json.loads(path.read_bytes())
        for seat in (0, 1):
            for index, step in enumerate(replay["steps"]):
                obs = deepcopy(step[seat]["observation"])
                obs.setdefault("step", index)
                if not 8 <= obs["day"] <= 24:
                    continue
                before = baseline["agent"](deepcopy(obs), replay["configuration"])
                after = adaptive["agent"](deepcopy(obs), replay["configuration"])
                if before != after:
                    records.append(
                        {
                            "replay": path.name,
                            "replay_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                            "seat": seat,
                            "day": obs["day"],
                            "hour": obs["hour"],
                            "baseline": before,
                            "adaptive": after,
                        }
                    )
    result = {
        "complete": True,
        "kind": "saved-observation action sensitivity; no stochastic games",
        "incumbent_sha256": INCUMBENT,
        "candidate_sha256": hashlib.sha256(source.encode()).hexdigest(),
        "changed_action_observations": len(records),
        "examples": records[:80],
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--diagnose", action="store_true")
    parser.add_argument(
        "--output", type=Path, default=Path("reports/results/phase4-adaptive-feed-diagnosis.json")
    )
    args = parser.parse_args()
    source = build()
    print(hashlib.sha256(source.encode()).hexdigest())
    if args.diagnose:
        print(json.dumps(diagnose(args.output), indent=2))


if __name__ == "__main__":
    main()
