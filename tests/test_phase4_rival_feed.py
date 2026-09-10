"""Rival-feed source relies only on public board state and compiles standalone."""

from scripts.phase4_rival_feed import build


def test_rival_feed_source_uses_visible_livestock_demand():
    source = build()
    namespace = {}
    exec(source, namespace)
    assert callable(namespace["agent"])
    assert 'obs["farms"][1 - obs["player"]]["tiles"]' in source
    assert "rival_animals >= len(animals) + 5" in source
