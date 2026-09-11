"""Carry observed animal care into the frozen public inventory forecast."""

import gzip
import hashlib
import inspect
from pathlib import Path

CONTROL = "fca083cdb5ac82dc4ad39a4227ef60ca57c948f819b565804aa706994f8e61ba"
FLOOR_CONTROL = "4ae6a08b45efd9c05c17c584ff2d65aa647f74041ade7c6360ff21a8aef8d6bb"


def animal_supply(tile, day, animal_specs, care_rate=0.8):
    """Expected new output, assuming daily feeding and timely collection.

    Observed held goods remain the caller's separate next-day delivery. Future
    care retains the incumbent's 0.8 intensity; care already completed today is
    known. Production consumes the prior bank before today's care is credited.
    """
    _, first, interval, cap, _, _ = animal_specs[tile["animal"]]
    bank = tile.get("pending_care_bonus", 0)
    events = []
    for current in range(day, 29):
        age = current + 1 - tile["placed_day"]
        if age >= first and (age - first) % interval == 0:
            events.append((current + 1, min(cap, 1 + bank)))
            bank = 0
        bank += 1.0 if current == day and tile.get("cared_today") else care_rate
    return tuple(events)


def build(*, floor_forecast=False):
    root = Path(__file__).resolve().parents[1]
    digest = FLOOR_CONTROL if floor_forecast else CONTROL
    raw = gzip.decompress((root / "reports/sources" / f"{digest}.py.gz").read_bytes())
    assert hashlib.sha256(raw).hexdigest() == digest
    source = raw.decode()
    original = """                    for future in range(day + 1, 30):
                        age = future - tile["placed_day"]
                        if age >= first and (age - first) % interval == 0:
                            # Imperfect future care/collection is a scenario assumption.
                            arrivals[future][item] += min(cap, 1 + 0.8 * interval)"""
    assert source.count(original) == 1
    source = source.replace(
        original,
        "                    for future, units in animal_supply(tile, day, animal_specs):\n"
        "                        arrivals[future][item] += units",
    )
    assert source.count("def forecast_inventory(") == 1
    source = source.replace(
        "def forecast_inventory(",
        inspect.getsource(animal_supply) + "\n\ndef forecast_inventory(",
        1,
    )
    compile(source, "care_bank_forecast_candidate", "exec")
    return source
