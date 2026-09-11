"""Reserve minimum drought obligations before optional yield and collection work."""

import gzip
import hashlib
from pathlib import Path

CONTROL = "fca083cdb5ac82dc4ad39a4227ef60ca57c948f819b565804aa706994f8e61ba"


def apply_minimum_water(source):
    """Keep mandatory WATER executable without optional fertilizer or harvest.

    The existing fleet still jointly reserves feed, water, creation inputs and
    routes. Acknowledged watering releases its target for subsequent optional
    work. Existing melon and startup hiring protection remain unchanged.
    """
    marker = (
        "        rushed = ("
        if "        rushed = (" in source
        else "        if operations and value > 0:\n            liquid = False"
    )
    assert source.count(marker) == 1
    source = source.replace(
        marker,
        """        if (
            required and isinstance(tile, dict) and tile.get("kind") == "PLANT"
            and tile.get("crop") != "MELON"
            and any(op == "WATER" for _, op, _ in operations)
        ):
            # Neither purchased fertilizer nor today's held product is a
            # prerequisite for preventing drought death and future yield loss.
            operations = [(target, "WATER", None)]
            value = crop_value_left(tile)
"""
        + marker,
    )
    marker = """                if hour + cost > end:
                    continue
                if any(amount > available[item] + old_need[item] for item, amount in need.items()):
                    continue"""
    assert source.count(marker) == 1
    source = source.replace(
        marker,
        """                water_obligation = bundle["required"] and any(
                    op == "WATER" for _, op, _ in bundle["ops"]
                )
                shortfall = hour + cost > end or any(
                    amount > available[item] + old_need[item] for item, amount in need.items()
                )
                if water_obligation and shortfall:
                    # A retained optional visit must not block a newly feasible
                    # minimum service route. Preserve all feed, water, creation
                    # and annual harvest commitments, including their inputs.
                    minimal = []
                    for operation in operations:
                        target, op, _ = operation
                        tile = tile_at(target)
                        optional_harvest = (
                            op == "HARVEST" and isinstance(tile, dict)
                            and tile.get("crop") in CROPS and CROPS[tile["crop"]][3] > 0
                        )
                        if op in ("FERTILIZE", "CARE", "COLLECT_FERTILIZER", "DROP") or optional_harvest:
                            continue
                        minimal.append(operation)
                    operations = minimal
                    cost, need, seed_use, _ = route_cost(worker, operations)
"""
        + marker,
    )
    compile(source, "minimum_water_obligations", "exec")
    return source


def build(*, base=CONTROL):
    root = Path(__file__).resolve().parents[1]
    raw = gzip.decompress((root / "reports/sources" / f"{base}.py.gz").read_bytes())
    assert hashlib.sha256(raw).hexdigest() == base
    return apply_minimum_water(raw.decode())
