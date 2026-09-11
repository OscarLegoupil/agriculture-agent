"""Expedite physical delivery when visible rival output threatens the quote."""

import inspect

from experiments.daily_routes import build as fleet_build

from kaggriculture.agent.competitive import ANIMALS, BASE, default_price_parameters, inventory_quote


def urgent_products(obs):
    """A public-output stress, not a forecast of hidden opponent orders.

    Melons retain the established opening race. Other commodities qualify only
    when presently held rival output could lower their quote by at least 20%.
    We assume that visible stock can reach market; actual routes remain observed.
    """
    market = obs["market"]
    specs = market.get("params") or default_price_parameters()
    supply = {}
    for row in obs["farms"][1 - obs["player"]]["tiles"]:
        for tile in row:
            if not isinstance(tile, dict):
                continue
            product = ANIMALS[tile["animal"]][4] if "animal" in tile else tile.get("crop")
            if product in BASE:
                supply[product] = supply.get(product, 0) + tile.get("yield_units", 0)
    selected = {"MELON"}
    for product, amount in supply.items():
        if product == "WHEAT" or market["prices"][product] <= 1 or not amount:
            continue
        stressed = inventory_quote(market["inventory"][product] + amount, specs[product])
        if stressed < 0.8 * market["prices"][product]:
            selected.add(product)
    return selected


def build():
    source = fleet_build(cereal=True, budget_seconds=0.150)

    def replace(old, new, count=1):
        nonlocal source
        assert source.count(old) == count, (old, source.count(old))
        source = source.replace(old, new)

    replace("def daily_routes(", inspect.getsource(urgent_products) + "\n\ndef daily_routes(")
    replace(
        '    prices = obs["market"]["prices"]\n    hire_runway',
        '    prices = obs["market"]["prices"]\n    rush = urgent_products(obs)\n    hire_runway',
    )
    # Identify products without changing collection, pickup or shared-stock rules.
    replace(
        'tile_at(target).get("crop") == "MELON"',
        '(ANIMALS[tile_at(target)["animal"]][4] if "animal" in tile_at(target) else tile_at(target).get("crop")) in rush',
        3,
    )
    replace(
        'bool(inventories[worker].get("MELON", 0))',
        "any(inventories[worker].get(item, 0) for item in rush)",
    )
    replace(
        'if inventories[worker].get("MELON", 0) or any(',
        "if any(inventories[worker].get(item, 0) for item in rush) or any(",
    )
    replace(
        "        if operations and value > 0:\n            liquid = False",
        "        rushed = (isinstance(tile, dict) and\n"
        '                  (ANIMALS[tile["animal"]][4] if "animal" in tile else tile.get("crop")) in rush\n'
        '                  and any(op == "HARVEST" for _, op, _ in operations))\n'
        '        if rushed and tile.get("crop") != "MELON":\n'
        "            # Finish same-visit feeding/watering prerequisites, then deliver.\n"
        "            # Other care and manure work is reconsidered after the route.\n"
        "            operations = [operation for operation in operations\n"
        '                          if operation[1] in ("FEED", "FERTILIZE", "WATER", "HARVEST")]\n'
        '            product = ANIMALS[tile["animal"]][4] if "animal" in tile else tile["crop"]\n'
        '            value = min(value, tile["yield_units"] * prices[product])\n'
        "        if operations and value > 0:\n            liquid = False",
    )
    replace(
        "                    premium=isinstance(tile, dict)\n"
        '                    and tile.get("crop") == "MELON"\n'
        '                    and any(op == "HARVEST" for _, op, _ in operations),',
        "                    premium=rushed,",
    )
    replace('        if item != "MELON":', "        if item not in urgent_products(obs):")
    compile(source, "market_collection_candidate", "exec")
    return source
