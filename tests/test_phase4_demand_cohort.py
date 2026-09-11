"""Demand-ranked cohorts preserve only the bridge-crop portion of the opening."""

import gzip
import hashlib
from pathlib import Path

from scripts.phase4_demand_cohort import INCUMBENT, build


def test_demand_cohort_removes_forced_strawberry_but_keeps_opening_bridge():
    source = build()
    assert 'else "STRAWBERRY"' not in source
    assert "if day < 3:" in source
    assert 'cohort_crop = "WHEAT" if planned["WHEAT"] < 7 else "MELON"' in source
    namespace = {}
    exec(source, namespace)
    assert callable(namespace["agent"])
    raw = gzip.decompress((Path("reports/sources") / f"{INCUMBENT}.py.gz").read_bytes())
    assert hashlib.sha256(raw).hexdigest() == INCUMBENT
