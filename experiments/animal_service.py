"""Finite-season service choices for sunk livestock under public price scenarios.

The small daily DP is exact for care, starvation and held-product transitions.
Prices are exogenous scenarios, and collection is assumed feasible every day.
Consequently its value is a diagnostic comparison, not achievable farm profit.
"""

from __future__ import annotations

import gzip
import hashlib
import inspect
import json
import sys
import time
from functools import cache
from pathlib import Path

from kaggriculture.agent.competitive import ANIMALS, CROPS, SHOPS, forecast_inventory

INCUMBENT = "64fe323936dc9494add413eb956b0294658a88efe28572332c94676c68a09325"
_ANIMAL_SERVICES = {}


def animal_dp(
    tile,
    day,
    product_prices,
    feed_prices,
    fertilizer_prices,
    *,
    work_price=4.0,
    travel_actions=0.0,
    deadline=None,
    daily_service=False,
):
    """Return today's feed/care choice and its finite-horizon service value.

    Existing product is collected before dusk on every day: this matches the
    deployed harvest policy and does not grant an unimplemented timing option.
    Feed has its sale opportunity cost even when already in our inventory.
    Each harvest/manure visit charges an action and a shared delivery action;
    feed adds one quarter of a bulk pickup. Travel is an explicit supplied
    amortization assumption. No day-30 production or asset salvage is valued.
    """
    if any(len(prices) != 30 - day for prices in (product_prices, feed_prices, fertilizer_prices)):
        raise ValueError("Price scenarios must cover today through day 29 only")
    _, first, interval, cap, _, _ = ANIMALS[tile["animal"]]
    born = tile["placed_day"]
    initial_fed, initial_cared = tile["fed_today"], tile["cared_today"]
    initial_manure = tile["fertilizer_available"]
    visited = 0

    @cache
    def solve(today, unfed, bank, held):
        nonlocal visited
        visited += 1
        if visited % 64 == 0 and deadline is not None and time.perf_counter() >= deadline:
            raise TimeoutError("animal service search budget")
        offset = today - day
        fed_before = initial_fed if today == day else False
        cared_before = initial_cared if today == day else False
        manure = initial_manure if today == day else True
        next_event = born + first
        if next_event <= today:
            next_event += (1 + (today - next_event) // interval) * interval
        useful = next_event <= 29 or held > 0
        choices = ((False, False), (True, False), (True, True))
        if daily_service:
            choices = ((useful and today < 29, useful and today < 29),)
        elif today == 29:
            choices = ((False, False),)
        best = None
        for feed, care in choices:
            fed, cared = fed_before or feed, cared_before or care
            actual_feed, actual_care = int(feed and not fed_before), int(care and not cared_before)
            # CARE may be issued before feed by the real worker controller,
            # but it only banks a unit if that animal ends the day fed.
            if care and not fed:
                continue
            harvest = held > 0
            for collect in (False, True) if manure and today < 29 else (False,):
                effort = 1.25 * actual_feed + actual_care + int(harvest) + int(collect)
                if harvest or collect:
                    effort += 1  # one common product delivery
                if effort:
                    effort += travel_actions
                value = held * product_prices[offset] - actual_feed * feed_prices[offset]
                value += int(collect) * fertilizer_prices[offset] - work_price * effort
                future = (0.0, 0, 0, 0, 0)
                if today < 29:
                    next_unfed = 0 if fed else unfed + 1
                    if next_unfed < 2:
                        next_bank, next_held = bank, 0
                        age = today + 1 - born
                        if age >= first and (age - first) % interval == 0:
                            next_held = min(cap, 1 + (bank if fed else 0))
                            next_bank = 0
                        if fed and cared:
                            next_bank += 1
                        future = solve(today + 1, next_unfed, next_bank, next_held)
                        value += future[0]
                result = (
                    value,
                    actual_feed + future[1],
                    actual_care + future[2],
                    int(harvest) + future[3],
                    int(collect) + future[4],
                    bool(feed),
                    bool(care),
                )
                # Equal values prefer fewer costly services, then no care.
                rank = (value, -result[1], -result[2], not care, not feed)
                if best is None or rank > best[0]:
                    best = rank, result
        return best[1]

    result = solve(day, tile["consecutive_unfed"], tile["pending_care_bonus"], tile["yield_units"])
    return dict(
        value=result[0],
        feed_units=result[1],
        care_actions=result[2],
        harvest_actions=result[3],
        manure_actions=result[4],
        feed=result[5],
        care=result[6],
        states=visited,
    )


def animal_service_decisions(obs, animals):
    """Replan once daily; retain a cheap incumbent decision before the budget."""
    player, day, step = obs["player"], obs["day"], obs["step"]
    if day < 16:
        return {}
    state = _ANIMAL_SERVICES.get(player)
    if not state or state["day"] != day or step <= state["step"]:
        state = dict(day=day, step=step, decisions={})
        _ANIMAL_SERVICES[player] = state
    state["step"] = step
    decisions = state["decisions"]
    deadline = time.perf_counter() + 0.080
    missing = [
        entry for entry in animals if (entry[0], entry[1], entry[2]["placed_day"]) not in decisions
    ]
    if missing:
        _, traces = forecast_inventory(obs, CROPS, ANIMALS, SHOPS)
        prices = obs["market"]["prices"]
        scenarios = {
            item: [prices[item], *(0.5 * prices[item] + 0.5 * quote for quote in quotes)]
            for item, quotes in traces.items()
        }
        for x, y, tile in missing:
            key = (x, y, tile["placed_day"])
            fallback = dict(feed=day < 29, care=day < 29)
            decisions[key] = fallback
            if time.perf_counter() >= deadline:
                print("animal_service_budget_fallback", file=sys.stderr)
                break
            try:
                # Nearby herd visits share pickup and depot travel. This is a
                # workload shadow-price assumption, not an exact fleet route.
                neighbors = sum(abs(x - xx) + abs(y - yy) <= 2 for xx, yy, _ in animals)
                half = len(obs["farms"][player]["tiles"]) // 2
                depot_distance = min(
                    abs(x - xx) + abs(y - yy) for xx in (half - 1, half) for yy in (half - 1, half)
                )
                decisions[key] = animal_dp(
                    tile,
                    day,
                    scenarios[ANIMALS[tile["animal"]][4]],
                    scenarios["WHEAT"],
                    scenarios["FERTILIZER"],
                    travel_actions=2 * depot_distance / max(1, neighbors),
                    deadline=deadline,
                )
            except TimeoutError:
                print("animal_service_budget_fallback", file=sys.stderr)
                break
    result = {}
    for x, y, tile in animals:
        decision = dict(
            decisions.get((x, y, tile["placed_day"]), dict(feed=day < 29, care=day < 29))
        )
        # The DP assumes collection occurs. Never use that hypothetical sale
        # to permit an actual escape while products remain on the tile.
        if tile["yield_units"] and tile["consecutive_unfed"] and day < 29:
            decision["feed"] = True
        result[(x, y)] = decision
    return result


def build():
    root = Path(__file__).resolve().parents[1]
    raw = gzip.decompress((root / "reports/sources" / f"{INCUMBENT}.py.gz").read_bytes())
    assert hashlib.sha256(raw).hexdigest() == INCUMBENT
    source = raw.decode()
    marker = '    feed_need = sum(not t["fed_today"] for _, _, t in animals) if day < 29 else 0'
    assert source.count(marker) == 1
    source = source.replace(
        marker,
        """    services = animal_service_decisions(obs, animals)
    feed_need = sum(not tile["fed_today"] and services.get((x, y), {"feed": True})["feed"] for x, y, tile in animals) if day < 29 else 0""",
    )
    marker = '        if not tile["fed_today"] and useful:'
    assert source.count(marker) == 1
    source = source.replace(
        marker,
        '        if not tile["fed_today"] and useful and services.get((x, y), {"feed": True})["feed"]:',
    )
    marker = '        if not tile["cared_today"] and tile["fed_today"] and useful and p["care"]:'
    assert source.count(marker) == 1
    source = source.replace(
        marker,
        '        if not tile["cared_today"] and tile["fed_today"] and useful and p["care"] and services.get((x, y), {"care": True})["care"]:',
    )
    helpers = "from functools import cache\n\n_ANIMAL_SERVICES = {}\n\n"
    helpers += inspect.getsource(animal_dp) + "\n\n" + inspect.getsource(animal_service_decisions)
    source = source.replace("def agent(", helpers + "\n\ndef agent(")
    compile(source, "animal_service_candidate", "exec")
    return source


def checkpoint_bound(path, seat=0, days=(16, 20, 24)):
    """Compare service policies using each checkpoint alone, never its future."""
    raw = Path(path).read_bytes()
    replay = json.loads(raw)
    rows = []
    for day in days:
        step = next(
            step
            for step in replay["steps"]
            if step[0]["observation"].get("day") == day and step[0]["observation"].get("hour") == 0
        )
        obs = {**step[0]["observation"], **step[seat]["observation"], "player": seat}
        _, traces = forecast_inventory(obs, CROPS, ANIMALS, SHOPS)
        prices = obs["market"]["prices"]
        animals = [
            tile
            for row in obs["farms"][seat]["tiles"]
            for tile in row
            if isinstance(tile, dict) and "animal" in tile
        ]
        for scenario in ("constant", "public_blend"):
            quotes = {
                item: [
                    prices[item],
                    *(
                        [prices[item]] * (29 - day)
                        if scenario == "constant"
                        else [0.5 * prices[item] + 0.5 * value for value in traces[item]]
                    ),
                ]
                for item in prices
            }
            baseline, alternative = [], []
            for tile in animals:
                args = (
                    tile,
                    day,
                    quotes[ANIMALS[tile["animal"]][4]],
                    quotes["WHEAT"],
                    quotes["FERTILIZER"],
                )
                baseline.append(animal_dp(*args, daily_service=True))
                alternative.append(animal_dp(*args))
            rows.append(
                dict(
                    day=day,
                    seat=seat,
                    scenario=scenario,
                    animals=len(animals),
                    daily_value=sum(result["value"] for result in baseline),
                    selective_value=sum(result["value"] for result in alternative),
                    daily_feed=sum(result["feed_units"] for result in baseline),
                    selective_feed=sum(result["feed_units"] for result in alternative),
                    daily_care=sum(result["care_actions"] for result in baseline),
                    selective_care=sum(result["care_actions"] for result in alternative),
                )
            )
    return dict(
        replay=str(path),
        replay_sha256=hashlib.sha256(raw).hexdigest(),
        environment_version=replay["module_version"],
        source_sha256=hashlib.sha256(build().encode()).hexdigest(),
        assumptions=dict(
            work_price=4,
            travel_actions=0,
            feasible_daily_collection=True,
            exogenous_prices=True,
            additive_checkpoints=False,
        ),
        checkpoints=rows,
    )


if __name__ == "__main__":
    if len(sys.argv) > 1:
        print(
            json.dumps(
                checkpoint_bound(sys.argv[1], int(sys.argv[2]) if len(sys.argv) > 2 else 0),
                indent=2,
            )
        )
    else:
        print(hashlib.sha256(build().encode()).hexdigest())
