"""Finite crop calendars, marginal sale impact, and explicit work charges."""

import argparse
import hashlib
import inspect
import json
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

from benchmark import episode, provenance, snapshot
from phase2_logistics import replace
from phase2_market_model import forecast_inventory


def cohort_calendar(spec, planting_day, fertilize):
    """Ideal feasible servicing; fertilizer precedes WATER on one-shot crops."""
    _, first, last, interval, cap = spec
    units = 0 if interval else 1
    dry = 1  # Official fresh plants require water on their planting day.
    active = -1
    previous_water = False
    sales, operations = [], []
    for age in range(30 - planting_day):
        absolute_day = planting_day + age
        if (
            interval
            and age >= first
            and (age - first) % interval == 0
            and (age - first) // interval < cap
        ):
            units = min(cap, units + (2 if previous_water and active >= age - 1 else 1))
        growth = (
            ((last + 1) // 2 <= age <= last)
            if not interval
            else (
                age + 1 >= first
                and (age + 1 - first) % interval == 0
                and (age + 1 - first) // interval < cap
            )
        )
        watered = False
        if absolute_day < 29 and (dry or growth):
            if growth and fertilize and active < age and units < cap:
                operations.append((age, "FERTILIZE"))
                active = age + 2
            operations.append((age, "WATER"))
            watered = True
            if not interval and growth:
                units = min(cap, units + (2 if active >= age else 1))
        desired = 2 if interval else min(cap, 1 + last - (last + 1) // 2 + 1)
        if (
            age >= first
            and units
            and (units >= desired or absolute_day == 29 or (not interval and age >= last))
        ):
            sales.append((age, units))
            operations.append((age, "HARVEST"))
            units = 0
            if not interval:
                break
        if interval and age >= first + (cap - 1) * interval and not units:
            if absolute_day < 27:
                operations.append((age + 1, "DIG"))
            break
        dry = 0 if watered else dry + 1
        previous_water = watered
    return sales, operations


def cohort_value(
    crop,
    spec,
    day,
    travel,
    fertilizer_price,
    fertilize,
    inventory_trace,
    price_spec,
    additional,
    seed_owned,
    quote,
    objective,
):
    sales, operations = cohort_calendar(spec, day, fertilize)
    if not sales:
        return float("-inf")
    receipts = 0.0
    already_sold = 0
    for age, units in sales:
        offset = max(0, min(len(inventory_trace) - 1, age - 1))
        # Existing cohorts are in the baseline trace; only newly considered
        # same-day cohorts enter this marginal block of sale quantities.
        inventory = inventory_trace[offset] + already_sold * (additional + 1) + units * additional
        receipts += sum(quote(inventory + unit, price_spec) for unit in range(units))
        already_sold += units
    fertilizer = sum(op == "FERTILIZE" for _, op in operations)
    visits = len({age for age, _ in operations}) + 1
    work = 1 + len(operations)  # planting plus tile work, in worker actions
    work += visits  # one marginal neighboring-tile move per service visit
    work += fertilizer / 4 * (travel + 1)  # shared four-unit input trips
    work += already_sold / 5 * (travel + 1)  # shared five-unit delivery trips
    action_price = 4.0  # cash per worker action, including travel
    profit = (
        receipts
        - (0 if seed_owned else spec[0])
        - fertilizer * fertilizer_price
        - action_price * work
    )
    return profit if objective == "profit" else profit / (sales[-1][0] + 1)


def build(base, objective, recurring_only=False):
    source = base.read_text()
    inventory = inspect.getsource(forecast_inventory)
    inventory = inventory[: inventory.index("    first_sale =")]
    inventory = inventory.replace("def forecast_inventory(", "def cohort_market_inventory(")
    inventory = inventory.replace(
        "traces[item].append(inventory_quote(inventory[item], parameters[item]))",
        "traces[item].append(inventory[item])",
    )
    inventory += "    return traces\n"
    functions = (
        inventory
        + "\n"
        + inspect.getsource(cohort_calendar)
        + "\n"
        + inspect.getsource(cohort_value)
    )
    source = replace(source, "def agent(", functions + "\n\ndef agent(")
    source = replace(
        source,
        "    planned = Counter(crops)",
        '    planned = Counter(crops)\n    cohort_inventory = cohort_market_inventory(obs, CROPS, ANIMALS, SHOPS) if room and free_cells and day < 28 else {}\n    cohort_prices = obs["market"].get("params") or default_price_parameters()',
    )
    old = """crop_value(
                crop, day, forecast[crop] / (1 + planned[crop] * 0.025), fert_price, use_fert
            )"""
    new = f"""cohort_value(
                crop, CROPS[crop], day, min(distance((x, y), s) for s in shed_tiles),
                fert_price, use_fert, cohort_inventory[crop], cohort_prices[crop],
                max(0, planned[crop] - crops[crop]), seeds.get(crop, 0) > 0,
                inventory_quote, {objective!r}
            )"""
    source = replace(source, old, new)
    if recurring_only:
        source = replace(
            source,
            'p["fertilize"]\n            and growth',
            'p["fertilize"]\n            and bool(interval)\n            and growth',
        )
        source = replace(
            source,
            "fert_price, use_fert, cohort_inventory[crop]",
            "fert_price, use_fert and bool(CROPS[crop][3]), cohort_inventory[crop]",
        )
    return source


def verify():
    from kaggle_environments.envs.kaggriculture import kaggriculture as game

    checked = []
    for crop, data in game.CROPS.items():
        spec = (
            data["seed"],
            data["first_yield_day"],
            data["max_yield_day"],
            data["interval"],
            data["max_yield"],
        )
        for day in (0, 17, 25):
            for fertilize in (False, True):
                sales, operations = cohort_calendar(spec, day, fertilize)
                farm = game._new_farm(10, 3000)
                farm["farmer"] = [0, 0]
                private = game._new_private()
                private["inventories"][0] = {"FERTILIZER": 20}
                farm["tiles"][0][0] = game._new_plant(crop, day, 24)
                actual = []
                for age in range(30 - day):
                    for target_age, operation in operations:
                        if target_age != age:
                            continue
                        before = private["inventories"][0].get(crop, 0)
                        game._apply_unit_action(farm, private, 0, [operation], 10, day + age, 24)
                        after = private["inventories"][0].get(crop, 0)
                        if operation == "HARVEST":
                            actual.append((age, after - before))
                    if day + age < 29:
                        game._daily_refresh_plants(farm, day + age, 24)
                assert actual == sales, (crop, day, fertilize, actual, sales)
                checked.append(
                    dict(
                        crop=crop,
                        planting_day=day,
                        fertilize=fertilize,
                        sales=sales,
                        operations=operations,
                    )
                )
    output = Path("data/interim/phase3-economics/calendar-contracts.json")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps({"official_calendars_checked": len(checked), "cases": checked}, indent=2)
    )
    print(
        f"{len(checked)} crop calendars match official WATER/FERTILIZE/HARVEST and daily transitions"
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--verify", action="store_true")
    parser.add_argument("--objective", choices=("rate", "profit"), default="rate")
    parser.add_argument("--recurring-only", action="store_true")
    parser.add_argument("--workers", type=int, default=2)
    args = parser.parse_args()
    if args.verify:
        verify()
        return
    base = Path(Path("data/raw/phase2-best-path.txt").read_text().strip())
    assert (
        hashlib.sha256(base.read_bytes()).hexdigest()
        == "0098d9e4f77e2420cb4a09abd47e49f5160009cd0818ae37a793bc3e419ffc4b"
    )
    name = args.objective + ("_recurring" if args.recurring_only else "")
    content = build(base, args.objective, args.recurring_only).encode()
    digest = hashlib.sha256(content).hexdigest()
    path = Path("data/interim/phase3-economics") / name / digest / "main.py"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
    opponents = ["data/raw/reference-seyam/main.py", "data/raw/reference-cok/main.py"]
    manifest = {
        **provenance([str(base), *opponents]),
        "base": str(base),
        "candidate": str(path),
        "sha256": digest,
        "snapshot": snapshot(path),
        "objective": args.objective,
        "recurring_only": args.recurring_only,
        "action_price": 4,
        "complete": False,
        "episodes": [],
    }
    output = Path(f"data/interim/phase3-economics/{name}-results.json")
    tasks = [
        (str(path), opponent, seed, seat, None)
        for opponent in opponents
        for seed in (0, 2000)
        for seat in (0, 1)
    ]
    with ProcessPoolExecutor(max_workers=args.workers) as pool:
        for row in pool.map(episode, tasks):
            manifest["episodes"].append(row)
            output.write_text(json.dumps(manifest, indent=2))
            print(
                row["opponent"],
                row["seed"],
                row["seat"],
                row["cash"] - row["opponent_cash"],
                flush=True,
            )
    assert hashlib.sha256(path.read_bytes()).hexdigest() == digest
    assert len(manifest["episodes"]) == len(tasks)
    assert len({(r["opponent"], r["seed"], r["seat"]) for r in manifest["episodes"]}) == len(tasks)
    manifest["completion_verification"] = {
        "expected_games": len(tasks),
        "candidate_sha256_verified": True,
        "all_statuses_done": all(
            all(s == "DONE" for s in r["statuses"]) for r in manifest["episodes"]
        ),
    }
    manifest["complete"] = True
    output.write_text(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
