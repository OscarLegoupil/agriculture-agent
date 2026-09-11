"""Admit the best currently funded crop on the frozen early cohort policy."""

import gzip
import hashlib
import inspect
from pathlib import Path

from kaggriculture.agent.competitive import CROPS

INCUMBENT = "9a83bb475173e00d1b5e2b28dada9c472e9e751139a5493ddbf1d3e5eb6a4652"


def financed_crop_values(values, seeds, admissions, cash, seed_orders, day):
    """Exclude seed obligations the current decision cannot fund.

    Admissions include both observed stock and already funded purchase orders.
    Newly purchased stock remains unavailable to this action's worker tasks.
    The caller's cash has already paid its preceding hires and other orders.
    """
    reserve = 30 if day < 2 else 200
    return {
        crop: value
        for crop, value in values.items()
        if seeds.get(crop, 0) > admissions[crop]
        or (cash > CROPS[crop][0] + reserve and seed_orders[crop] < 4)
    }


def build():
    root = Path(__file__).resolve().parents[1]
    raw = gzip.decompress((root / "reports/sources" / f"{INCUMBENT}.py.gz").read_bytes())
    assert hashlib.sha256(raw).hexdigest() == INCUMBENT
    source = raw.decode()
    marker = "        crop = max(values, key=lambda c: values[c])"
    assert source.count(marker) == 1
    source = source.replace(
        marker,
        "        if day >= 3:\n"
        "            values = financed_crop_values(values, seeds, opportunity_admissions, cash, seed_orders, day)\n"
        "            if not values:\n"
        "                continue\n" + marker,
    )
    marker = "        if seeds.get(crop, 0) > 0:"
    assert source.count(marker) == 1
    source = source.replace(
        marker,
        "        if seeds.get(crop, 0) > (opportunity_admissions[crop] if day >= 3 else 0):",
    )
    assert source.count("def agent(") == 1
    source = source.replace(
        "def agent(", inspect.getsource(financed_crop_values) + "\n\ndef agent("
    )
    compile(source, "crop_opportunity_financed_candidate", "exec")
    return source
