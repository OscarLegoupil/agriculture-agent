"""Screen finite-harvest annual fertilizer admission on the startup policy.

The small trace assumes ideal daily watering and the ordinary yield target;
the startup policy can additionally harvest wheat early during cash/feed
shortages. Its 3% daily cash discount and four-coin worker-action value are
explicit model assumptions, not measured constants. Preserve the screened
artifact before changing these approximations.
"""

import argparse
import hashlib
import inspect
import json
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

from benchmark import episode, provenance, snapshot
from phase2_logistics import replace
from phase3_startup import build as startup

BASE_SHA256 = "dbd2a8418b57573cb6084712bfbcd2d18245fac83fcf18bc1ab7c39345b5d955"


def annual_harvest(spec, age, held, days_left, fertilize):
    """Small ideal-water trace ending at the controller's first admitted harvest."""
    _, first, last, interval, cap = spec
    if interval:
        raise ValueError("Annual trace requires a one-shot crop")
    target = min(cap, 1 + last - (last + 1) // 2 + 1)
    water_actions = 0
    for offset in range(min(days_left, max(0, last - age)) + 1):
        now = age + offset
        if (last + 1) // 2 <= now <= last:
            held = min(cap, held + (2 if fertilize and offset <= 2 else 1))
            water_actions += 1
        if now >= first and (held >= target or offset == days_left):
            return held, offset, water_actions
    return 0, days_left, water_actions


def annual_fertilizer_value(spec, age, held, days_left, price, fert_price, extra_travel):
    plain, delay_plain, work_plain = annual_harvest(spec, age, held, days_left, False)
    fed, delay_fed, work_fed = annual_harvest(spec, age, held, days_left, True)
    # Explicit 3% daily working-capital discount: earlier cash can fund servicing.
    sale_gain = price * (fed / 1.03**delay_fed - plain / 1.03**delay_plain)
    return sale_gain + 4 * (work_plain - work_fed) - fert_price - 4 * (extra_travel + 1)


def build():
    source = startup("startup_fert_reserve")
    assert hashlib.sha256(source.encode()).hexdigest() == BASE_SHA256
    helpers = "\n\n".join(inspect.getsource(f) for f in (annual_harvest, annual_fertilizer_value))
    source = replace(source, "def agent(", helpers + "\n\ndef agent(")
    source = replace(
        source,
        '        if not tile["watered_today"] and not terminal and (tile["consecutive_unwatered"] or growth):',
        """        annual_fert = False
        if (not interval and growth and not terminal and not tile["watered_today"]
                and tile["fertilized_until_day"] < day and yield_units < cap):
            routes = []
            for worker, position in enumerate(positions):
                direct = distance(position, (x, y))
                if inventories[worker].get("FERTILIZER", 0):
                    routes.append((direct, 0))
                elif shed.get("FERTILIZER", 0):
                    via = min(distance(position, s) + distance(s, (x, y)) for s in shed_tiles)
                    routes.append((via + 1, max(0, via - direct) + 1))
            if routes:
                travel, extra = min(routes)
                useful_value = annual_fertilizer_value(
                    CROPS[crop], age, yield_units, 29 - day,
                    min(prices[crop], forecast[crop]), fert_price, extra)
                # Leave time for the separate fertilizer and watering actions.
                annual_fert = useful_value > 0 and hour + travel + 2 <= 22
                if annual_fert:
                    task(x, y, "FERTILIZE", 120 + min(80, useful_value), "FERTILIZER")
        if not annual_fert and not tile["watered_today"] and not terminal and (tile["consecutive_unwatered"] or growth):""",
    )
    compile(source, "annual_fertilizer.py", "exec")
    return source


def probe():
    from kaggle_environments.envs.kaggriculture import kaggriculture as game

    namespace = {}
    exec(build(), namespace)
    cases = 0
    for crop, age in (("WHEAT", 2), ("CARROT", 2), ("MELON", 6)):
        for fertilizer in (False, True):
            farm = game._new_farm(10, 3000)
            farm["farmer"] = [4, 4]
            private = game._new_private()
            private["inventories"][0] = {"FERTILIZER": 1}
            tile = game._new_plant(crop, 0, 24)
            farm["tiles"][4][4] = tile
            expected, offset, _ = annual_harvest(
                namespace["CROPS"][crop], age, 1, 29 - age, fertilizer
            )
            for day in range(age, age + offset + 1):
                if day == age and fertilizer:
                    game._apply_unit_action(farm, private, 0, ["FERTILIZE"], 10, day, 24)
                game._apply_unit_action(farm, private, 0, ["WATER"], 10, day, 24)
                if day == age + offset:
                    game._apply_unit_action(farm, private, 0, ["HARVEST"], 10, day, 24)
                else:
                    game._daily_refresh_plants(farm, day, 24)
            assert private["inventories"][0][crop] == expected
            cases += 1
    wheat = namespace["CROPS"]["WHEAT"]
    assert annual_fertilizer_value(wheat, 2, 1, 20, 100, 1, 0) > 0
    assert annual_fertilizer_value(wheat, 2, 1, 20, 20, 100, 0) < 0
    print(json.dumps({"official_harvest_cases": cases, "economic_admission_cases": 2}))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--probe", action="store_true")
    parser.add_argument("--workers", type=int, default=2)
    args = parser.parse_args()
    if args.probe:
        probe()
        return
    content = build().encode()
    digest = hashlib.sha256(content).hexdigest()
    path = Path("data/interim/phase3-fertilizer") / digest / "main.py"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
    opponents = [f"data/raw/reference-{name}/main.py" for name in ("seyam", "cok")]
    manifest = {
        **provenance([str(path), *opponents]),
        "base_sha256": BASE_SHA256,
        "candidate_snapshot": snapshot(path),
        "hypothesis": "Annual fertilizer only when executable incremental harvest value repays inputs and work",
        "complete": False,
        "episodes": [],
    }
    tasks = [
        (str(path), opponent, seed, seat, None)
        for opponent in opponents
        for seed in (0, 2001)
        for seat in (0, 1)
    ]
    output = Path("data/raw/phase3-fertilizer.json")
    with ProcessPoolExecutor(max_workers=args.workers) as pool:
        for row in pool.map(episode, tasks):
            manifest["episodes"].append(row)
            output.write_text(json.dumps(manifest, indent=2))
            print(
                row["opponent"],
                row["seed"],
                row["seat"],
                row["cash"],
                row["opponent_cash"],
                flush=True,
            )
    assert len(manifest["episodes"]) == len(tasks)
    assert hashlib.sha256(path.read_bytes()).hexdigest() == digest
    manifest["complete"] = True
    manifest["completion_validation"] = {
        "expected_scenarios": len(tasks),
        "artifact_sha256": digest,
    }
    output.write_text(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
