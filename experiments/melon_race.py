"""Prepare opening melons before maturity and race their first delivery.

This experimental package links input reservation, affordable procurement,
fertilizer application, harvesting and same-turn selling. It preserves the
incumbent production choices and exposes component ablations to the evaluator.
"""

import gzip
import hashlib
import inspect
from pathlib import Path

from scripts.phase4_delivery import immediate_delivery_sales

INCUMBENT = "64fe323936dc9494add413eb956b0294658a88efe28572332c94676c68a09325"


def melon_fertilizer_needed(tile, day, reserve=False):
    """One application on age 7/8 reaches cap before the age-10 harvest.

    Reserving inputs starts one day earlier. A three-day application remains
    sufficient even if that day's watering happened before fertilizer arrived.
    Existing fertilization and already capped crops need no new input.
    """
    age = day - tile["planted_day"]
    return (
        tile["crop"] == "MELON"
        and (6 if reserve else 7) <= age <= 8
        and tile["yield_units"] < 6
        and tile["fertilized_until_day"] < day
        and tile["planted_day"] + 10 <= 28
    )


def build(fertilizer=True, race=True, same_turn_sales=True):
    """Build a self-contained candidate from the immutable incumbent bytes."""
    raw = gzip.decompress((Path("reports/sources") / f"{INCUMBENT}.py.gz").read_bytes())
    assert hashlib.sha256(raw).hexdigest() == INCUMBENT
    source = raw.decode()

    def replace(old, new):
        nonlocal source
        assert source.count(old) == 1, old
        source = source.replace(old, new)

    if fertilizer:
        replace("def agent(obs:", inspect.getsource(melon_fertilizer_needed) + "\n\ndef agent(obs:")
        replace(
            '    fert_price = prices["FERTILIZER"]',
            '    fert_price = prices["FERTILIZER"]\n'
            "    melon_inputs = sum(melon_fertilizer_needed(tile, day, reserve=True)\n"
            "                       for _, _, tile in plants)\n"
            "    melon_due = sum(melon_fertilizer_needed(tile, day)\n"
            "                    for _, _, tile in plants)",
        )
        replace(
            "        quantity = max(0, shed.get(item, 0) - reserve)",
            '        if item == "FERTILIZER" and melon_inputs:\n'
            "            reserve = max(reserve, max(0, melon_inputs - carried[item]))\n"
            "        quantity = max(0, shed.get(item, 0) - reserve)",
        )
        replace(
            "    if purchase and cash > ANIMALS[purchase][0] + 150:",
            "    # Partial purchases can complete with today's manure receipts.\n"
            "    # Feed and real hires have already reserved their working capital.\n"
            '    melon_short = max(0, melon_due - stock["FERTILIZER"])\n'
            "    melon_buy = min(melon_short, max(0, int((cash - 150) // (fert_price + 1))))\n"
            '    if melon_buy and len(market) < cfg.get("maxMarketOrdersPerTurn", 10):\n'
            '        market.append(["BUY_PRODUCT", "FERTILIZER", melon_buy])\n'
            "        cash -= melon_buy * (fert_price + 1)\n"
            "    if purchase and cash > ANIMALS[purchase][0] + 150:",
        )
        replace(
            '        if (\n            p["fertilize"]\n            and growth',
            "        if melon_fertilizer_needed(tile, day):\n"
            '            task(x, y, "FERTILIZE", 260, "FERTILIZER")\n'
            '        if (\n            p["fertilize"]\n            and growth',
        )
        replace(
            '    need_fert = max(0, min(12, fert_tasks) - stock["FERTILIZER"])',
            "    ordered_fert = sum(order[2] for order in market\n"
            '                       if order[:2] == ["BUY_PRODUCT", "FERTILIZER"])\n'
            '    need_fert = max(0, min(12, fert_tasks) - stock["FERTILIZER"] - ordered_fert)',
        )
    if race:
        replace(
            "                140\n                if water_before_harvest",
            "                min(480, max(140, yield_units * prices[crop] * 0.5))\n"
            '                if water_before_harvest and crop == "MELON"\n'
            "                else 140\n                if water_before_harvest",
        )
        replace(
            '                    125 if terminal or (expiry >= 0 and obs["step"] + 4 >= expiry) else 70,',
            "                    min(480, max(70, yield_units * prices[crop] * 0.5))\n"
            '                    if crop == "MELON" and not terminal\n'
            '                    else 125 if terminal or (expiry >= 0 and obs["step"] + 4 >= expiry) else 70,',
        )
        replace(
            "            if i in deadline_actions:\n                continue\n            home = min(shed_tiles",
            '            if i in deadline_actions or inventories[i].get("MELON", 0):\n'
            "                continue\n            home = min(shed_tiles",
        )
        replace(
            '            and ((pos in shed_tiles and load >= 3) or load >= p["return_load"] or end_return)',
            '            and ((pos in shed_tiles and load >= 3) or load >= p["return_load"]\n'
            '                 or inv.get("MELON", 0) or end_return)',
        )
    if same_turn_sales:
        projector = inspect.getsource(immediate_delivery_sales)
        eligible = (
            'if item not in ("CARROT", "TOMATO", "STRAWBERRY", "MELON", "EGG", "MILK", "WOOL"):'
        )
        assert projector.count(eligible) == 1
        # Keep the tested worker-order projection; advance only this crop.
        projector = projector.replace(eligible, 'if item != "MELON":')
        replace("def agent(obs:", projector + "\n\ndef agent(obs:")
        replace(
            '        "market": market[: cfg.get("maxMarketOrdersPerTurn", 10)],',
            '        "market": immediate_delivery_sales(obs, cfg, actions, market),',
        )
    compile(source, "melon_race", "exec")
    return source
