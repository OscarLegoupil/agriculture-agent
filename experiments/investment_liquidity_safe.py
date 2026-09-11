"""Repair maintenance starvation in the frozen capital-delivery experiments."""

import gzip
import hashlib
from pathlib import Path

from experiments.market_collection_safe import apply_safe_priorities


def build(*, seed_capital=True):
    digest = (
        "0994c15084911da9c2c54e48bf9f79a1f773aa66447c6cd51ea5ac1c400cf4c4"
        if seed_capital
        else "10d90b31d3aedc9f60d808314eb0d5e97217ad7c81932c3dcb300cb999dc874d"
    )
    root = Path(__file__).resolve().parents[1]
    source = gzip.decompress((root / "reports/sources" / f"{digest}.py.gz").read_bytes())
    assert hashlib.sha256(source).hexdigest() == digest
    return apply_safe_priorities(source.decode(), investment_pressure=True)
