"""Reserve maintenance before newly introduced market or investment urgency."""

import gzip
import hashlib
from pathlib import Path

MARKET_COLLECTION = "a283c29d5ac221d6eff14d23960f08ad09dd8797b8bcbbbf37407d873b01dc5f"


def apply_safe_priorities(source, *, market_pressure=False, investment_pressure=False):
    """Transform a frozen experimental source; preserve melon and hire urgency.

    New pressure gets its own tier after required watering/feeding. It cannot
    erase those prerequisites, replace a retained maintenance route with DROP,
    or prevent mandatory insertion into a non-melon collection route.
    """
    if not market_pressure and not investment_pressure:
        raise ValueError("Select the experimental pressure to repair")

    def replace(old, new, count=1):
        nonlocal source
        assert source.count(old) == count, (old, source.count(old))
        source = source.replace(old, new)

    if market_pressure:
        replace(
            "                    premium=rushed,",
            '                    premium=isinstance(tile, dict) and tile.get("crop") == "MELON"\n'
            '                    and any(op == "HARVEST" for _, op, _ in operations),\n'
            '                    expedited=rushed and tile.get("crop") != "MELON",',
        )
        old = """            if any(inventories[worker].get(item, 0) for item in rush) or any(
                op == "HARVEST"
                and isinstance(tile_at(target), dict)
                and (ANIMALS[tile_at(target)["animal"]][4] if "animal" in tile_at(target) else tile_at(target).get("crop")) in rush
                for target, op, _ in old_ops
            ):
                continue"""
        replace(
            old,
            """            protected_melon = inventories[worker].get("MELON", 0) or any(
                op == "HARVEST" and isinstance(tile_at(target), dict)
                and tile_at(target).get("crop") == "MELON"
                for target, op, _ in old_ops
            )
            if protected_melon:
                continue
            if not bundle["required"] and (any(inventories[worker].get(item, 0) for item in rush) or any(
                op == "HARVEST" and isinstance(tile_at(target), dict)
                and (ANIMALS[tile_at(target)["animal"]][4] if "animal" in tile_at(target) else tile_at(target).get("crop")) in rush
                for target, op, _ in old_ops
            )):
                continue""",
        )
        replace(
            """                if melon_index is not None and any(
                    op != "DROP" for _, op, _ in operations[melon_index + 1 :]
                ):""",
            """                if melon_index is not None and any(
                    op != "DROP" for _, op, _ in operations[melon_index + 1 :]
                ) and (not bundle["required"] or any(
                    op == "HARVEST" and isinstance(tile_at(target), dict)
                    and tile_at(target).get("crop") == "MELON"
                    for target, op, _ in operations
                )):""",
        )
    if investment_pressure:
        replace(
            """    liquidity_needed = (
        len(farm["hands"]) < target_hands and farm["money"] < hire_runway and hour < 8
    ) or investment_liquidity_possible(
        obs, cfg, positions, inventories, tasks, access, investment_cash_need
    )""",
            """    hire_liquidity = (
        len(farm["hands"]) < target_hands and farm["money"] < hire_runway and hour < 8
    )
    investment_liquidity = investment_liquidity_possible(
        obs, cfg, positions, inventories, tasks, access, investment_cash_need
    )
    liquidity_needed = hire_liquidity or investment_liquidity""",
        )
        replace(
            """        if liquidity_needed and liquid_cargo > 0:
            home = min(access, key=lambda depot: (distance(positions[worker], depot), depot))
            plans[worker] = {"ops": [(home, "DROP", None)], "expected": {}}""",
            """        if liquidity_needed and liquid_cargo > 0:
            home = min(access, key=lambda depot: (distance(positions[worker], depot), depot))
            if hire_liquidity:
                plans[worker] = {"ops": [(home, "DROP", None)], "expected": {}}
            else:
                retained = plans.get(worker, {"ops": [], "expected": {}})
                delivered = one_delivery(worker, [*retained["ops"], (home, "DROP", None)])
                if hour + route_cost(worker, delivered)[0] <= end:
                    plans[worker] = {"ops": delivered, "expected": retained["expected"]}""",
        )
        replace(
            "                        operations, value, required, liquid = collection, receipts, False, True",
            """                        if hire_liquidity:
                            operations, value, required, liquid = collection, receipts, False, True
                        else:
                            operations = [operation for operation in operations if operation[1] != "CARE"]
                            value = value if required else min(value, receipts)
                            liquid = True""",
        )
        replace(
            '            if liquidity_needed and any(op == "DROP" for _, op, _ in old_ops):',
            '            if liquidity_needed and any(op == "DROP" for _, op, _ in old_ops) and (hire_liquidity or not bundle["required"]):',
        )
        replace(
            "            if liquidity_needed and liquid_cargo > 0:\n                continue",
            '            if liquidity_needed and liquid_cargo > 0 and (hire_liquidity or not bundle["required"]):\n                continue',
        )
    legacy = (
        'candidate["liquid"] and hire_liquidity' if investment_pressure else 'candidate["liquid"]'
    )
    expedited = 'candidate.get("expedited", False)'
    if investment_pressure:
        expedited += ' or candidate["liquid"]'
    replace(
        """                0
                if candidate["liquid"]
                else 1
                if candidate["premium"]
                else 2
                if candidate["required"]
                else 3,""",
        f"""                0
                if {legacy}
                else 1
                if candidate["premium"]
                else 2
                if candidate["required"]
                else 3
                if {expedited}
                else 4,""",
    )
    legacy = 'bundle["liquid"] and hire_liquidity' if investment_pressure else 'bundle["liquid"]'
    expedited = 'bundle.get("expedited", False)'
    if investment_pressure:
        expedited += ' or bundle["liquid"]'
    replace(
        """                rank = (
                    (cost, extra, worker, slot)
                    if bundle["premium"] or bundle["liquid"] or bundle["commissioning"]
                    else (max(cost, other_finish), extra, worker, slot)
                    if bundle["required"]
                    else (-score, cost, worker, slot)
                )""",
        f"""                rank = (
                    (cost, extra, worker, slot)
                    if bundle["premium"] or ({legacy}) or bundle["commissioning"]
                    else (max(cost, other_finish), extra, worker, slot)
                    if bundle["required"]
                    else (cost, extra, worker, slot)
                    if {expedited}
                    else (-score, cost, worker, slot)
                )""",
    )
    pressure = 'bool(rush - {"MELON"})' if market_pressure else "False"
    if investment_pressure:
        pressure = f"({pressure} or investment_liquidity) and not hire_liquidity"
    replace(
        """                cost, need, seed_use, _ = route_cost(worker, operations)
                if hour + cost > end:
                    continue""",
        f"""                cost, need, seed_use, _ = route_cost(worker, operations)
                if hour + cost > end and bundle["required"] and {pressure}:
                    protected_melon = inventories[worker].get("MELON", 0) or any(
                        op == "HARVEST" and isinstance(tile_at(target), dict)
                        and tile_at(target).get("crop") == "MELON"
                        for target, op, _ in operations
                    )
                    if not protected_melon:
                        # A new sale opportunity cannot make life-preserving
                        # service infeasible merely by requiring today's DROP.
                        operations = [operation for operation in operations if operation[1] != "DROP"]
                        cost, need, seed_use, _ = route_cost(worker, operations)
                if hour + cost > end:
                    continue""",
    )
    compile(source, "safe_collection_priorities", "exec")
    return source


def build():
    root = Path(__file__).resolve().parents[1]
    raw = gzip.decompress((root / "reports/sources" / f"{MARKET_COLLECTION}.py.gz").read_bytes())
    assert hashlib.sha256(raw).hexdigest() == MARKET_COLLECTION
    return apply_safe_priorities(raw.decode(), market_pressure=True)
