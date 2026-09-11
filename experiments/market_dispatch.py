"""Finite-season sale allocation for existing premium inventory.

The planner observes public farms and demand. It optimizes quantities over a
scenario, then replans; the scenario is not a prediction of future random shops.
"""

import gzip
import hashlib
import inspect
import sys
import time
from pathlib import Path

from kaggriculture.agent.competitive import (
    ANIMALS,
    CROPS,
    SHOPS,
    default_price_parameters,
    inventory_quote,
)

INCUMBENT = "64fe323936dc9494add413eb956b0294658a88efe28572332c94676c68a09325"


def dispatch_curve(inventories, spec, units, quote, horizon_penalty=0.025, deadline=None):
    """Exact quantity DP for one deterministic inventory scenario.

    inventories[t] excludes the stock being dispatched. Each earlier sale changes
    later inventory. The terminal state sells everything; no salvage is credited.
    Returns the number to sell now and the value of the optimized schedule.
    """
    immediate = sum(quote(inventories[0] + k, spec) for k in range(units))
    future = [float("-inf")] * units + [0.0]
    first = [0] * (units + 1)
    for delay in range(len(inventories) - 1, -1, -1):
        # Discount is a declared cash/forecast-risk penalty, not inferred demand.
        discount = 1 / (1 + horizon_penalty * delay)
        baseline = inventories[delay]
        marginal = [quote(baseline + k, spec) * discount for k in range(units)]
        prefix = [0.0]
        for value in marginal:
            prefix.append(prefix[-1] + value)
        current = [0.0] * (units + 1)
        for sold in range(units + 1):
            if deadline is not None and time.perf_counter() >= deadline:
                print("market_dispatch_budget_fallback", file=sys.stderr)
                return units, immediate
            best, amount = float("-inf"), 0
            for after in range(sold, units + 1):
                value = prefix[after] - prefix[sold] + future[after]
                # Earlier receipts win equal-value ties.
                if value >= best:
                    best, amount = value, after - sold
            current[sold], first[sold] = best, amount
        future = current
    return first[0], future[0]


def dispatch_sales(obs, action, forecast):
    """Receding-horizon dispatch under shared storage and capital constraints."""
    farm = obs["farms"][obs["player"]]
    if obs["day"] < 10 or obs["day"] >= 29 or farm["money"] < 8000:
        return action
    shed = obs["private"]["shed"]
    if not any(shed.get(item, 0) for item in ("WOOL", "MILK")):
        return action
    # Do not retain premium stock when current worker cargo needs the room.
    cargo = sum(sum(inv.values()) for inv in obs["private"]["inventories"])
    headroom = max(0, 100 - sum(shed.values()) - cargo - 25)
    if not headroom:
        return action
    predicted = forecast(obs, CROPS, ANIMALS, SHOPS)
    parameters = obs["market"].get("params") or default_price_parameters()
    opportunities = []
    deadline = time.perf_counter() + 0.08
    for item in ("WOOL", "MILK"):
        units = min(60, shed.get(item, 0))
        if not units:
            continue
        spec = parameters[item]
        scenario = [obs["market"]["inventory"][item]] + [row[item] for row in predicted]
        sell, value = dispatch_curve(scenario, spec, units, inventory_quote, deadline=deadline)
        immediate = sum(inventory_quote(scenario[0] + k, spec) for k in range(units))
        if units > sell and value > immediate:
            opportunities.append(((value - immediate) / (units - sell), item, units - sell))
    holds = {}
    for _, item, amount in sorted(opportunities, reverse=True):
        holds[item] = min(amount, headroom)
        headroom -= holds[item]
    orders = []
    for order in action["market"]:
        if order[0] == "SELL" and order[1] in holds:
            order = list(order)
            order[2] = max(0, order[2] - holds.pop(order[1]))
            if not order[2]:
                continue
        orders.append(order)
    return dict(action, market=orders)


def build():
    raw = gzip.decompress((Path("reports/sources") / f"{INCUMBENT}.py.gz").read_bytes())
    assert hashlib.sha256(raw).hexdigest() == INCUMBENT
    source = raw.decode()
    start, end = source.index("def forecast_inventory("), source.index("\ndef agent(")
    model = source[start:end].replace("def forecast_inventory(", "def dispatch_inventory(", 1)
    model = model.replace(
        "    traces: dict[str, list[int]] = {item: [] for item in inventory}",
        "    traces: dict[str, list[int]] = {item: [] for item in inventory}\n    inventory_states = []",
    )
    model = model.replace(
        "    first_sale = {item: spec[1] for item, spec in crop_specs.items()}",
        "        inventory_states.append(dict(inventory))\n    return inventory_states\n\n    first_sale = {item: spec[1] for item, spec in crop_specs.items()}",
    )
    model = model[: model.index("\n    first_sale =")]
    source = source.replace("def agent(", "def physical_agent(", 1)
    wrapper = """
def agent(obs, configuration=None):
    action = physical_agent(obs, configuration)
    if not obs.get("farms") or obs.get("player") not in (0, 1):
        return action
    return dispatch_sales(obs, action, dispatch_inventory)
"""
    source += "\n\n" + model + "\n\n" + inspect.getsource(dispatch_curve)
    source += "\n\n" + inspect.getsource(dispatch_sales) + wrapper
    compile(source, "market_dispatch", "exec")
    return source
