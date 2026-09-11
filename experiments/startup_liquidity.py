"""Fund inexpensive startup hands against already collectable manure.

This changes the capital reserve only for the first three cheap hires, while
there is observed revenue within one short delivery. Future production is not
collateral. All other investment and scheduling decisions remain the incumbent's.
"""

import gzip
import hashlib
import inspect
from pathlib import Path

INCUMBENT = "64fe323936dc9494add413eb956b0294658a88efe28572332c94676c68a09325"


def startup_hire_reserve(obs, index, wage):
    if not 1 <= obs["day"] <= 7 or index >= 3 or wage > 2:
        return 120
    farm = obs["farms"][obs["player"]]
    half = len(farm["tiles"]) // 2
    depots = [(half - 1, half - 1), (half, half - 1), (half - 1, half), (half, half)]
    collectable = 0
    for y, row in enumerate(farm["tiles"]):
        for x, tile in enumerate(row):
            if not isinstance(tile, dict) or not tile.get("fertilizer_available"):
                continue
            travel = min(abs(x - a) + abs(y - b) for a, b in depots)
            # Hire is available next turn; collect, return, DROP, then SELL.
            if obs["hour"] + 2 * travel + 4 < 20:
                collectable += obs["market"]["prices"]["FERTILIZER"]
    return 10 if collectable > 4 * wage else 120


def build():
    raw = gzip.decompress((Path("reports/sources") / f"{INCUMBENT}.py.gz").read_bytes())
    assert hashlib.sha256(raw).hexdigest() == INCUMBENT
    source = raw.decode()
    source = source.replace(
        "def agent(", inspect.getsource(startup_hire_reserve) + "\n\ndef agent(", 1
    )
    old = 'if index >= len(farm["hands"]) and cash > a + 120 and len(market) < 8:'
    assert source.count(old) == 1
    source = source.replace(
        old,
        'if index >= len(farm["hands"]) and cash > a + startup_hire_reserve(obs, index, a) and len(market) < 8:',
    )
    compile(source, "startup_liquidity", "exec")
    return source
