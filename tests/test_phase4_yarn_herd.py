"""The Yarn Store herd guard is observation-only and leaves the opening intact."""

from scripts.phase4_yarn_herd import build


def test_yarn_guard_compiles_and_uses_only_known_shop_demand():
    source = build()
    assert 'if "YARN_STORE" in obs["town"]["unlocked_shops"]:' in source
    assert 'desired["COW"] = 8' in source
    assert "if day < 8:" in source
    namespace = {}
    exec(source, namespace)
    assert callable(namespace["agent"])
