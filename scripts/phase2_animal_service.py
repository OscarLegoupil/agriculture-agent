"""Finite-season animal-service counterfactual on immutable v7.

Rejected standalone after 16 development games; saved evidence identifies
92512ba2f62f7ff6f58634dfae7112b00cdd2f3e3161abc3dd7a86d293935707.
The transition model is interpreter-checked. Its economic value remains an
upper bound: harvest is immediate, price is fixed at the current quote, and
the fertilizer reward includes the final refresh although v7's final-day
controller does not collect newly available fertilizer. Do not describe this
as an exact executable whole-farm planner or deploy it without new evidence.
"""

import argparse
import hashlib
import json
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

from benchmark import episode, provenance, snapshot
from phase2_logistics import DIGEST, INCUMBENT, replace

SERVICE = """
from functools import lru_cache


def animal_transition(age, unfed, bonus, feed, care, first, interval, cap):
    missed = 0 if feed else unfed + 1
    if missed >= 2:
        return None
    production = age + 1 >= first and (age + 1 - first) % interval == 0
    units = min(cap, 1 + (bonus if feed else 0)) if production else 0
    bank = 0 if production else bonus
    return missed, min(cap - 1, bank + int(feed and care)), units


@lru_cache(maxsize=65536)
def animal_future(day, age, animal, unfed, bonus, product_price, feed_price, fert_value):
    if day >= 29:
        return 0.0
    _, first, interval, cap, _, _ = ANIMALS[animal]
    best = 0.0  # Stop servicing an asset that cannot repay its remaining costs.
    for feed, care in ((0, 0), (1, 0), (1, 1)):
        transition = animal_transition(age, unfed, bonus, feed, care, first, interval, cap)
        if transition is None:
            continue
        missed, bank, units = transition
        reward = units * product_price - (4 if units else 0)
        reward += fert_value - feed * (feed_price + 4) - care * 4
        score = reward + animal_future(day + 1, age + 1, animal, missed, bank,
                                      product_price, feed_price, fert_value)
        best = max(best, score)
    return best


def animal_service(tile, day, prices):
    if day >= 29:
        return False, False
    animal = tile["animal"]
    _, first, interval, cap, product, _ = ANIMALS[animal]
    age = day - tile["placed_day"]
    # Coarse current quotes bound cache growth. No future shops or RNG are read.
    product_price = max(1, round(prices[product] / 20) * 20)
    feed_price = max(1, round(prices["WHEAT"] / 5) * 5)
    fert_value = max(0, round(prices["FERTILIZER"] / 10) * 10 - 6)
    bonus = min(cap - 1, tile.get("pending_care_bonus", 0))
    best, decision = -math.inf, (False, False)
    for feed, care in ((0, 0), (1, 0), (1, 1)):
        if tile["fed_today"] and not feed:
            continue
        if tile["cared_today"] and not care:
            continue
        transition = animal_transition(age, tile["consecutive_unfed"], bonus,
                                       feed, care, first, interval, cap)
        if transition is None:
            score = -tile.get("yield_units", 0) * product_price
        else:
            missed, bank, units = transition
            score = units * product_price - (4 if units else 0) + fert_value
            score -= (feed and not tile["fed_today"]) * (feed_price + 4)
            score -= (care and not tile["cared_today"]) * 4
            score += animal_future(day + 1, age + 1, animal, missed, bank,
                                   product_price, feed_price, fert_value)
        if score > best:
            best, decision = score, (bool(feed), bool(care))
    return decision


"""


def build():
    assert hashlib.sha256(INCUMBENT.read_bytes()).hexdigest() == DIGEST
    source = INCUMBENT.read_text()
    source = replace(source, "def agent(", SERVICE + "def agent(")
    source = replace(
        source,
        'feed_need = sum(not t["fed_today"] for _, _, t in animals) if day < 29 else 0',
        "service = {(x, y): animal_service(t, day, prices) for x, y, t in animals}\n"
        '    feed_need = sum(service[x, y][0] and not t["fed_today"] for x, y, t in animals)',
    )
    source = replace(
        source, 'max(0, len(animals) - carried["WHEAT"])', 'max(0, feed_need - carried["WHEAT"])'
    )
    source = replace(
        source,
        'if not tile["fed_today"] and useful:',
        'if not tile["fed_today"] and service[x, y][0]:',
    )
    source = replace(source, 'and useful and p["care"]:', 'and service[x, y][1] and p["care"]:')
    return source


def probe():
    """Compare every small transition to the official animal refresh."""
    from kaggle_environments.envs.kaggriculture import kaggriculture as game

    scope = {}
    exec(build(), scope)
    checks = 0
    for animal, spec in game.ANIMALS.items():
        for age in range(15):
            for missed in (0, 1):
                for bonus in range(spec["max_held"] + 2):
                    for feed, care in ((0, 0), (1, 0), (1, 1)):
                        farm = game._new_farm(10, 3000)
                        tile = game._new_animal(animal, 0)
                        farm["tiles"][0][0] = tile
                        tile.update(
                            consecutive_unfed=missed,
                            pending_care_bonus=bonus,
                            fed_today=bool(feed),
                            cared_today=bool(care),
                        )
                        expected = scope["animal_transition"](
                            age,
                            missed,
                            min(bonus, spec["max_held"] - 1),
                            feed,
                            care,
                            spec["first_yield_day"],
                            spec["interval"],
                            spec["max_held"],
                        )
                        game._daily_refresh_animals(farm, age)
                        actual = farm["tiles"][0][0]
                        assert (expected is None) == ("animal" not in actual)
                        if expected is not None:
                            assert expected == (
                                actual["consecutive_unfed"],
                                min(spec["max_held"] - 1, actual.get("pending_care_bonus", 0)),
                                actual["yield_units"],
                            )
                        checks += 1
    prices = dict(scope["BASE"], MILK=200, WOOL=200, WHEAT=20, FERTILIZER=20)
    tile = game._new_animal("COW", 0)
    assert scope["animal_service"](tile, 0, prices) == (False, False)
    tile["consecutive_unfed"] = 1
    assert scope["animal_service"](tile, 0, prices)[0]
    assert scope["animal_service"](tile, 29, prices) == (False, False)
    return {
        "official_transition_checks": checks,
        "opening_feed_deferred": True,
        "starvation_recovery": True,
        "scope": "ideal immediate harvesting; no field travel simulation",
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workers", type=int, default=2)
    parser.add_argument("--probe", action="store_true")
    parser.add_argument("--output", type=Path, default=Path("data/raw/phase2-animal-service.json"))
    args = parser.parse_args()
    if args.probe:
        print(json.dumps(probe(), indent=2))
        return
    opponents = [
        f"data/raw/reference-{name}/main.py" for name in ("lonespear", "gzm", "seyam", "cok")
    ]
    content = build().encode()
    digest = hashlib.sha256(content).hexdigest()
    path = Path("data/interim/phase2-animal-service") / digest / "main.py"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
    manifest = {
        **provenance([str(path), *opponents]),
        "hypothesis": "Finite-horizon animal service with ideal harvest upper bound",
        "candidate_snapshot": snapshot(path),
        "episodes": [],
    }
    tasks = [
        (str(path), opponent, seed, seat, None)
        for opponent in opponents
        for seed in (17, 103)
        for seat in (0, 1)
    ]
    with ProcessPoolExecutor(max_workers=args.workers) as pool:
        for row in pool.map(episode, tasks):
            manifest["episodes"].append(row)
            args.output.write_text(json.dumps(manifest, indent=2))
            print(
                row["opponent"],
                row["seed"],
                row["seat"],
                row["cash"],
                row["opponent_cash"],
                flush=True,
            )


if __name__ == "__main__":
    main()
