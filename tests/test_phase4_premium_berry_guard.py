"""Premium-berry guard remains a self-contained market-observation policy."""

from scripts.phase4_premium_berry_guard import build


def test_premium_guard_compiles_and_uses_public_price_only():
    source = build()
    namespace = {}
    exec(source, namespace)
    assert callable(namespace["agent"])
    assert 'prices["STRAWBERRY"] >= BASE["STRAWBERRY"] * 1.49' in source
