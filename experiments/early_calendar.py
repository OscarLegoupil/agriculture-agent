"""Opening herd capacity and demand-sensitive early crop admission experiments."""

from experiments.daily_routes import build as fleet_build


def build(*, early_herd=False, adaptive_crops=False):
    """Keep the bounded fleet executor; change the financed production calendar.

    Six early animals reserve their future sites before seed orders consume the
    opening quadrant. Adaptive crops retain the initial wheat/melon bridge, then
    use the parent's public-state crop ranking instead of prescribing 34 berries.
    These are development hypotheses, not selected production defaults.
    """
    source = fleet_build(cereal=True, budget_seconds=0.150)

    def replace(old, new):
        nonlocal source
        assert source.count(old) == 1, old
        source = source.replace(old, new)

    if early_herd:
        replace(
            "desired = dict(COW=2, SHEEP=2, GOOSE=0)", "desired = dict(COW=4, SHEEP=2, GOOSE=0)"
        )
        replace(
            '    room = max(0, p["crop_tiles"] - len(plants))',
            '    room = max(0, p["crop_tiles"] - len(plants))\n'
            "    if day < 8:\n"
            "        # Reserve six animal sites, including already occupied ones.\n"
            "        room = min(room, max(0, len(cells) - 6 - len(plants)))",
        )
    if adaptive_crops:
        replace(
            "        if day < 15:\n            cohort_crop = ",
            "        if day < 3:\n            cohort_crop = ",
        )
    compile(source, "early_calendar_candidate", "exec")
    return source
