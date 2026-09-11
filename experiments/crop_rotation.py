"""Preserve the financing berry cohort, then commission commercial wheat.

The failed combined calendar introduced wheat before funding berries. This
alternative preserves the opening and limits only additional long-lived cohorts;
it retains the incumbent herd, land geometry, labor and physical scheduler.
"""

import gzip
import hashlib
from pathlib import Path

INCUMBENT = "64fe323936dc9494add413eb956b0294658a88efe28572332c94676c68a09325"


def build(berries=34):
    if berries not in (30, 34):
        raise ValueError("Only the two declared production mixes are supported")
    raw = gzip.decompress((Path("reports/sources") / f"{INCUMBENT}.py.gz").read_bytes())
    assert hashlib.sha256(raw).hexdigest() == INCUMBENT
    source = raw.decode()
    old = '            cohort_crop = "WHEAT" if planned["WHEAT"] < 7 else "MELON" if day < 3 else "STRAWBERRY"'
    new = (
        '            cohort_crop = ("WHEAT" if planned["WHEAT"] < 7 else "MELON" if day < 3\n'
        f'                           else "STRAWBERRY" if planned["STRAWBERRY"] < {berries} else "WHEAT")'
    )
    assert source.count(old) == 1
    source = source.replace(old, new)
    # After long-cohort commissioning ends, annual selection remains price-aware;
    # feed opportunity value applies to the admitted commercial-wheat capacity.
    source = source.replace('    p = PARAMS', f'    p = dict(PARAMS, feed_grown={50 - berries})', 1)
    compile(source, "crop_rotation", "exec")
    return source
