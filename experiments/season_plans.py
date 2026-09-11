"""Executable seasonal production alternatives to independent asset admission.

These plans are original target calendars, not reference action tapes. Workers
still use the incumbent controller; realized commissioning is measured separately.
"""

import gzip
import hashlib
import inspect
from pathlib import Path

INCUMBENT = "64fe323936dc9494add413eb956b0294658a88efe28572332c94676c68a09325"


def season_targets(day, family):
    """Return cumulative animals and crop capacity; late assets have no resale."""
    final = {"wool": (6, 12), "dairy": (12, 6), "balanced": (8, 10)}[family]
    total = min(18, 4 + 2 * max(0, day - 2))
    sheep = min(final[1], max(2, round(total * final[1] / 18)))
    cows = min(final[0], max(2, total - sheep))
    wheat = 7 if day < 5 else 14 if day < 9 else 26
    # Long cohorts close before day15; wheat can rotate through the final week.
    return {"COW": cows, "SHEEP": sheep, "GOOSE": 0}, wheat, 38


def build(family="wool", scope="all"):
    raw = gzip.decompress((Path("reports/sources") / f"{INCUMBENT}.py.gz").read_bytes())
    assert hashlib.sha256(raw).hexdigest() == INCUMBENT
    source = raw.decode()

    def replace(old, new):
        nonlocal source
        assert source.count(old) == 1, old
        source = source.replace(old, new)

    replace("def agent(obs:", inspect.getsource(season_targets) + "\n\ndef agent(obs:")
    if scope == "all":
        replace("    p = PARAMS", "    p = dict(PARAMS, quadrants=4, crop_tiles=70)")
    replace(
        "    desired = dict.fromkeys(ANIMALS, 18)\n    if day < 8:\n        desired = dict(COW=2, SHEEP=2, GOOSE=0)",
        f"    desired, wheat_target, berry_target = season_targets(day, {family!r})\n    if day < 3:\n        desired = dict(COW=2, SHEEP=2, GOOSE=0)",
    )
    replace(
        "            revenue = events * (interval + 1) * forecast[product]",
        "            bonus = max(0, min(ANIMALS[animal][3], first) - interval - 1) if events else 0\n"
        "            revenue = (events * (interval + 1) + bonus) * forecast[product]\n"
        "            # Conservative collection credit, bounded by observed manure prices.\n"
        '            revenue += max(0, 28 - day) * min(fert_price, forecast["FERTILIZER"]) * 0.75',
    )
    replace(
        "                options.append((net / cost, animal))",
        "                # Complete the declared herd composition instead of repeatedly\n"
        "                # buying whichever species currently has the largest ROI.\n"
        "                deficit = (cap - counts[animal] - stock[animal]) / max(1, cap)\n"
        "                options.append((deficit, animal))",
    )
    if scope == "herd":
        # Preserve every opening decision; the structural package changed the
        # initial animal ordering even though its day3 aggregate herd matched.
        replace(
            '            feed_cost = (29 - day) * prices["WHEAT"]',
            "            if day < 3:\n"
            "                revenue = events * (interval + 1) * forecast[product]\n"
            '            feed_cost = (29 - day) * prices["WHEAT"]',
        )
        replace(
            "                options.append((deficit, animal))",
            "                options.append((net / cost if day < 3 else deficit, animal))",
        )
        compile(source, "herd_calendar", "exec")
        return source
    assert scope == "all"
    replace(
        '    target_hands = min(p["hands"], max(4, math.ceil(workload / 8)))\n    if day == 29:',
        "    commissioning = 8 if 3 <= day <= 8 else 4\n"
        '    target_hands = min(p["hands"], max(commissioning, math.ceil(workload / 8)))\n    if day == 29:',
    )
    return finish(source)


def finish(source):
    old = '''        if day < 15:
            cohort_crop = "WHEAT" if planned["WHEAT"] < 7 else "MELON" if day < 3 else "STRAWBERRY"'''
    new = """        if day < 25:
            cohort_crop = (
                "WHEAT" if planned["WHEAT"] < wheat_target
                else "MELON" if day < 3
                else "STRAWBERRY" if day < 15 and planned["STRAWBERRY"] < berry_target
                else "WHEAT"
            )"""
    assert source.count(old) == 1
    source = source.replace(old, new)
    # Stop reserving all unused acreage for additional berries once the funded
    # production plan is complete. Retain observed mature assets until harvested.
    old = '    room = max(0, p["crop_tiles"] - len(plants))'
    new = '    room = max(0, min(p["crop_tiles"], wheat_target + berry_target) - len(plants))'
    assert source.count(old) == 1
    source = source.replace(old, new)
    compile(source, "season_plan", "exec")
    return source
