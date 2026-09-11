"""Marginal livestock service decisions integrated with the capacity fleet.

The existing animal transition DP supplies the recurrence. This experiment
compares today's feed/care bundle with withholding both services, so held stock
and sunk future income are not credited again by the route scheduler. Future
prices and collection feasibility remain explicit approximations.
"""

from __future__ import annotations

import gzip
import hashlib
import inspect
import sys
import textwrap
import time
from functools import cache
from pathlib import Path

from experiments.animal_service import animal_dp

from kaggriculture.agent.competitive import ANIMALS, CROPS, SHOPS, forecast_inventory

CONTROL = "fca083cdb5ac82dc4ad39a4227ef60ca57c948f819b565804aa706994f8e61ba"
_FLEET_ANIMAL_SERVICES = {}


def _dp_source():
    """Reuse the tested recurrence, exposing its root counterfactual values."""
    source = inspect.getsource(animal_dp).replace("def animal_dp(", "def fleet_animal_dp(", 1)
    source = source.replace("    visited = 0", "    visited = 0\n    today_values = {}", 1)
    marker = "            for collect in (False, True) if manure and today < 29 else (False,):"
    assert source.count(marker) == 1
    source = source.replace(
        marker,
        "            collection_choices = ((bool(manure),) if today == day and today < 29\n"
        "                                  else (False, True) if manure and today < 29 else (False,))\n"
        "            for collect in collection_choices:",
        1,
    )
    marker = "                # Equal values prefer fewer costly services, then no care."
    assert source.count(marker) == 1
    source = source.replace(
        marker,
        "                if today == day:\n"
        "                    today_values[(actual_feed, actual_care)] = value\n" + marker,
        1,
    )
    marker = "    return dict(\n        value=result[0],"
    assert source.count(marker) == 1
    source = source.replace(
        marker,
        "    actual_feed = int(result[5] and not initial_fed)\n"
        "    actual_care = int(result[6] and not initial_cared)\n"
        "    service_gain = result[0] - today_values[(0, 0)]\n"
        "    # The fleet prices today's actual route. Undo only today's modeled\n"
        "    # service effort; keep feed opportunity cost and all future costs.\n"
        "    direct_work = 1.25 * actual_feed + actual_care\n"
        "    if direct_work and not (tile['yield_units'] or (initial_manure and day < 29)):\n"
        "        direct_work += travel_actions\n"
        "    return dict(\n"
        "        service_gain=service_gain,\n"
        "        service_credit=service_gain + work_price * direct_work,\n"
        "        today_values=today_values,\n"
        "        value=result[0],",
        1,
    )
    return source


_DP_NAMESPACE = {"cache": cache, "time": time, "ANIMALS": ANIMALS}
exec(_dp_source(), _DP_NAMESPACE)
fleet_animal_dp = _DP_NAMESPACE["fleet_animal_dp"]


def fleet_animal_decisions(obs, animals):
    """Daily public price scenarios; acknowledge executed services in each DP.

    Missing or timed-out decisions leave the incumbent fleet path available.
    Current-day collection is fixed to the existing collection task, rather
    than claiming an unimplemented immediate manure option. Future collection
    is still an optimistic feasible-visit assumption, not guaranteed income.
    """
    player, day, step = obs["player"], obs["day"], obs["step"]
    if step == 0:
        _FLEET_ANIMAL_SERVICES.pop(player, None)
    if day < 16:
        return {}
    state = _FLEET_ANIMAL_SERVICES.get(player)
    if not state or state["day"] != day or step < state["step"] or step == 0:
        state = dict(day=day, step=step, decisions={}, scenarios=None)
        _FLEET_ANIMAL_SERVICES[player] = state
    state["step"] = step
    if day == 29:
        return {
            (x, y): dict(feed=False, care=False, service_gain=0, service_credit=0)
            for x, y, _ in animals
        }
    deadline = time.perf_counter() + 0.080
    if state["scenarios"] is None:
        _, traces = forecast_inventory(obs, CROPS, ANIMALS, SHOPS)
        prices = obs["market"]["prices"]
        state["scenarios"] = {
            item: [prices[item], *(0.5 * prices[item] + 0.5 * quote for quote in quotes)]
            for item, quotes in traces.items()
        }
    scenarios = state["scenarios"]
    result = {}
    for x, y, tile in animals:
        identity = (
            x,
            y,
            tile["animal"],
            tile["placed_day"],
            tile["consecutive_unfed"],
            tile["pending_care_bonus"],
            tile["yield_units"],
            tile["fed_today"],
            tile["cared_today"],
            tile["fertilizer_available"],
        )
        if identity not in state["decisions"]:
            if time.perf_counter() >= deadline:
                print("fleet_animal_budget_fallback", file=sys.stderr)
                break
            neighbors = sum(abs(x - xx) + abs(y - yy) <= 2 for xx, yy, _ in animals)
            half = len(obs["farms"][player]["tiles"]) // 2
            depot = min(
                abs(x - xx) + abs(y - yy) for xx in (half - 1, half) for yy in (half - 1, half)
            )
            try:
                state["decisions"][identity] = fleet_animal_dp(
                    tile,
                    day,
                    scenarios[ANIMALS[tile["animal"]][4]],
                    scenarios["WHEAT"],
                    scenarios["FERTILIZER"],
                    travel_actions=2 * depot / max(1, neighbors),
                    deadline=deadline,
                )
            except TimeoutError:
                print("fleet_animal_budget_fallback", file=sys.stderr)
                break
        result[(x, y)] = state["decisions"][identity]
    return result


def build(*, enabled=True):
    root = Path(__file__).resolve().parents[1]
    raw = gzip.decompress((root / "reports/sources" / f"{CONTROL}.py.gz").read_bytes())
    assert hashlib.sha256(raw).hexdigest() == CONTROL
    source = raw.decode()
    if not enabled:
        return source
    marker = '    feed_need = sum(not t["fed_today"] for _, _, t in animals) if day < 29 else 0'
    assert source.count(marker) == 1
    source = source.replace(
        marker,
        marker + "\n    services = fleet_animal_decisions(obs, animals)\n"
        '    service_feed_need = sum(not tile["fed_today"] and services.get((x, y), {"feed": True})["feed"]\n'
        "                            for x, y, tile in animals) if day < 29 else 0",
        1,
    )
    marker = '    buy_feed = max(0, feed_need - stock["WHEAT"])'
    assert source.count(marker) == 1
    source = source.replace(marker, '    buy_feed = max(0, service_feed_need - stock["WHEAT"])', 1)
    marker = '        reserve = max(0, len(animals) - carried["WHEAT"]) if item == "WHEAT" and day < 29 else 0'
    assert source.count(marker) == 1
    source = source.replace(
        marker,
        '        reserve = max(0, (service_feed_need if day >= 16 else len(animals)) - carried["WHEAT"]) if item == "WHEAT" and day < 29 else 0',
        1,
    )
    marker = '        if not tile["fed_today"] and useful:'
    assert source.count(marker) == 1
    source = source.replace(
        marker,
        '        if not tile["fed_today"] and services.get((x, y), {"feed": useful})["feed"]:',
        1,
    )
    marker = '        if not tile["cared_today"] and tile["fed_today"] and useful and p["care"]:'
    assert source.count(marker) == 1
    source = source.replace(
        marker,
        '        if not tile["cared_today"] and tile["fed_today"] and services.get((x, y), {"care": useful})["care"] and p["care"]:',
        1,
    )
    marker = "    target_hands,\n):"
    assert source.count(marker) == 1
    source = source.replace(marker, "    target_hands,\n    services=None,\n):", 1)
    marker = "        target_hands,\n    )"
    assert source.count(marker) == 1
    source = source.replace(marker, "        target_hands, services,\n    )", 1)
    marker = '        if op == "WATER":\n'
    assert source.count(marker) == 1
    source = source.replace(
        marker,
        "        service = (services or {}).get(target)\n"
        '        if op in ("FEED", "CARE") and service is not None and isinstance(tile, dict) and "animal" in tile:\n'
        '            if not service[op.lower()] or (op == "CARE" and not tile["fed_today"]):\n'
        "                return False\n" + marker,
        1,
    )
    start = source.index("            next_day, product, residual = animal_value(tile)")
    end = source.index('            if "COLLECT_FERTILIZER" in choices:', start)
    old = source[start:end]
    new = """            service = (services or {}).get(target)
            if service is not None:
                product = ANIMALS[tile["animal"]][4]
                feeding = tile["fed_today"]
                if "FEED" in choices and service["feed"] and not feeding and day < 29:
                    operations.append((target, "FEED", None))
                    feeding = True
                    required = bool(tile["consecutive_unfed"])
                if "HARVEST" in choices:
                    operations.append((target, "HARVEST", None))
                    value += tile["yield_units"] * prices[product]
                if feeding and service["care"] and not tile["cared_today"] and day < 29:
                    operations.append((target, "CARE", None))
                if any(op in ("FEED", "CARE") for _, op, _ in operations):
                    value += max(0, service["service_credit"])
            else:
"""
    source = source[:start] + new + textwrap.indent(old, "    ") + source[end:]
    helpers = "from functools import cache\n\n_FLEET_ANIMAL_SERVICES = {}\n\n"
    helpers += _dp_source() + "\n\n" + inspect.getsource(fleet_animal_decisions)
    source = source.replace("def agent(", helpers + "\n\ndef agent(", 1)
    compile(source, "fleet_animal_service_candidate", "exec")
    return source
