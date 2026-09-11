"""Price-floor-aware public supply scenarios, isolated from retirement planning.

The cohort quantities and expected future shops are the incumbent assumptions.
Only sale execution changes: product sold for $1 does not enter market stock.
Three intraday delivery schedules expose timing uncertainty; they are scenarios,
not achievable bounds or forecasts of the opponent's private orders.
"""

from __future__ import annotations

import ast
import gzip
import hashlib
import inspect
import math
from pathlib import Path

from kaggriculture.agent.competitive import (
    default_price_parameters,
    forecast_inventory,
    inventory_quote,
)

CONTROL = "fca083cdb5ac82dc4ad39a4227ef60ca57c948f819b565804aa706994f8e61ba"


def floor_sale_inventory(inventory, quantity, parameters):
    """Stock after sequential sales, including a final expected fractional unit.

    Quotes are monotone in inventory under the official pricing functions. A
    binary search finds how many unit quotes exceed $1; sales after that point
    earn their floor receipt but leave the inventory unchanged.
    """
    if quantity < 0:
        raise ValueError("Sale quantity must be nonnegative")
    if not quantity or inventory_quote(inventory, parameters) == 1:
        return inventory
    count = math.ceil(quantity)
    if inventory_quote(inventory + count - 1, parameters) > 1:
        return inventory + quantity
    low, high = 0, count
    while low < high:
        midpoint = (low + high) // 2
        if inventory_quote(inventory + midpoint, parameters) > 1:
            low = midpoint + 1
        else:
            high = midpoint
    return inventory + min(quantity, low)


def floor_price_scenarios(obs, arrivals, animals, shops, timing=None):
    """Public daily supply under early, spread and late delivery scenarios.

    Shop demand occurs six times daily, and center demand once. Animal feed
    procurement is spread over those six opportunities. The terminal horizon
    ends on day 29. Quantities may be fractional because future care, delivery
    and not-yet-observed shops are expectations, not realized hidden state.
    """
    day = obs["day"]
    market = obs["market"]
    parameters = market.get("params") or default_price_parameters()
    timings = (timing,) if timing else ("early", "spread", "late")
    if any(value not in ("early", "spread", "late") for value in timings):
        raise ValueError("Unknown delivery timing")
    inventories = [dict(market["inventory"]) for _ in timings]
    traces = {item: [] for item in market["inventory"]}
    initial_shops = obs["town"]["unlocked_shops"]
    for future in range(day + 1, 30):
        shop_demand = {item: 0.0 for item in traces}
        for shop in initial_shops:
            products = shops[shop]
            for item in products:
                shop_demand[item] += 2 if len(products) == 1 else 1
        extra = max(0, min(8 - len(initial_shops), future // 3 - day // 3))
        for products in shops.values():
            for item in products:
                shop_demand[item] += extra * (2 if len(products) == 1 else 1) / len(shops)
        for inventory, delivery in zip(inventories, timings, strict=True):
            for item in inventory:
                supply = arrivals[future][item] + (animals * 0.5 if item == "FERTILIZER" else 0)
                amount = inventory[item]
                for tick in range(6):
                    # Early deliveries precede hour-zero town consumption.
                    if delivery == "early" and tick == 0:
                        amount = floor_sale_inventory(amount, supply, parameters[item])
                    amount -= shop_demand[item]
                    if tick == 0 and item != "FERTILIZER":
                        amount -= 1
                    if item == "WHEAT":
                        amount -= animals / 6
                    # Other deliveries follow the known consumption opportunity.
                    if delivery == "spread":
                        amount = floor_sale_inventory(amount, supply / 6, parameters[item])
                    elif delivery == "late" and tick == 5:
                        amount = floor_sale_inventory(amount, supply, parameters[item])
                inventory[item] = amount
        for item in traces:
            traces[item].append(
                sum(inventory_quote(inv[item], parameters[item]) for inv in inventories)
                / len(inventories)
            )
    return traces


def _forecast_source():
    source = inspect.getsource(forecast_inventory)
    start = source.index("    traces: dict[str, list[int]]")
    end = source.index("    first_sale =", start)
    return (
        source[:start]
        + "    traces = floor_price_scenarios(obs, arrivals, animals, shops)\n"
        + source[end:]
    )


def build(*, animal_service=False):
    """Return a standalone capacity control with only the forecast replaced."""
    if animal_service:
        from experiments.fleet_animal_service import build as service_build

        source = service_build()
    else:
        root = Path(__file__).resolve().parents[1]
        raw = gzip.decompress((root / "reports/sources" / f"{CONTROL}.py.gz").read_bytes())
        assert hashlib.sha256(raw).hexdigest() == CONTROL
        source = raw.decode()
    node = next(
        node
        for node in ast.parse(source).body
        if isinstance(node, ast.FunctionDef) and node.name == "forecast_inventory"
    )
    original = ast.get_source_segment(source, node)
    helpers = inspect.getsource(floor_sale_inventory) + "\n\n"
    helpers += inspect.getsource(floor_price_scenarios) + "\n\n" + _forecast_source()
    assert source.count(original) == 1
    source = source.replace(original, helpers, 1)
    compile(source, "floor_forecast_candidate", "exec")
    return source
