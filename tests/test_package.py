from kaggriculture import __version__


def test_version() -> None:
    assert isinstance(__version__, str)
    assert __version__.count(".") == 2
