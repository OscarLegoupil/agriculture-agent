"""The conditional feed builder is a self-contained, deployable policy source."""

import hashlib

from scripts.phase4_adaptive_feed import build


def test_adaptive_feed_source_compiles_and_uses_unforced_relative_value():
    source = build()
    namespace = {}
    exec(source, namespace)
    assert callable(namespace["agent"])
    assert "unforced_wheat > unforced_berries > 0" in source
    assert len(hashlib.sha256(source.encode()).hexdigest()) == 64
