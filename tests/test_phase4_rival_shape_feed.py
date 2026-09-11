"""The rival-shape feed switch reads only public board livestock composition."""

from scripts.phase4_rival_shape_feed import build


def test_rival_shape_feed_compiles_and_has_no_identity_lookup():
    source = build()
    assert 'rival = obs["farms"][1 - obs["player"]]' in source
    assert "rival_cows >= 6 and rival_cows >= rival_sheep + 2" in source
    assert "reference-cok" not in source
    namespace = {}
    exec(source, namespace)
    assert callable(namespace["agent"])
