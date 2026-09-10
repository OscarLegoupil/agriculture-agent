"""The wool-demand opening release has bounded public-state scope."""

from scripts.phase4_yarn_opening import build


def test_yarn_opening_compiles_and_keeps_the_default_opening_cap():
    source = build()
    assert 'desired = dict(COW=2, SHEEP=2, GOOSE=0)' in source
    assert 'if day >= 3 and "YARN_STORE" in obs["town"]["unlocked_shops"]:' in source
    assert 'desired = dict(COW=4, SHEEP=8, GOOSE=0)' in source
    namespace = {}
    exec(source, namespace)
    assert callable(namespace["agent"])
