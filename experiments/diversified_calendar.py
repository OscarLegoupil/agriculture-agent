"""Test early tomato capacity while retaining the financed wheat opening."""

from experiments.daily_routes import build as fleet_build


def build(*, compact_herd=False):
    """Split 34 long-crop positions between berries and earlier tomato cohorts.

    The incumbent's seven-wheat capital bridge remains prescribed. This changes
    the season production mix without relying on unseen rival future plantings
    in a point forecast. The separate compact-herd ablation caps livestock at
    four throughout the season, freeing both sites and investment capital.
    """
    source = fleet_build(cereal=True, budget_seconds=0.150)
    old = 'else "STRAWBERRY" if planned["STRAWBERRY"] < 34 else "WHEAT")'
    assert source.count(old) == 1
    source = source.replace(
        old,
        'else "STRAWBERRY" if planned["STRAWBERRY"] < 16\n'
        '                           else "TOMATO" if planned["TOMATO"] < 18 else "WHEAT")',
    )
    if compact_herd:
        old = "and len(animals) + sum(stock[a] for a in ANIMALS) < 18"
        assert source.count(old) == 1
        source = source.replace(old, "and len(animals) + sum(stock[a] for a in ANIMALS) < 4")
    compile(source, "diversified_calendar", "exec")
    return source
