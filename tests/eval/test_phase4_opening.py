"""First-cohort care slack respects official care consumption and cap timing."""

from copy import deepcopy

from scripts.phase4_opening import care_priority


def animal_data(game, name):
    data = game.ANIMALS[name]
    return (data["cost"], data["first_yield_day"], data["interval"], data["max_held"], "", "")


def tile(name, placed=0):
    return dict(
        animal=name,
        placed_day=placed,
        fed_today=True,
        cared_today=False,
        consecutive_unfed=0,
        yield_units=0,
        pending_care_bonus=0,
        fertilizer_available=False,
    )


def test_initial_sheep_precede_cows_and_both_can_reach_first_cap():
    from kaggle_environments.envs.kaggriculture import kaggriculture as game

    animals = [tile("COW"), tile("COW"), tile("SHEEP"), tile("SHEEP")]
    priority = [care_priority(t, 0, animal_data(game, t["animal"])) for t in animals]
    selected = sorted(range(4), key=lambda i: priority[i], reverse=True)[:2]
    assert selected == [2, 3]
    farm = {"tiles": [[deepcopy(t) for t in animals] for _ in range(4)]}
    # A square official board, with only one active row.
    farm["tiles"][1:] = [[None] * 4 for _ in range(3)]
    first_yields = {}
    for day in range(8):
        for index, t in enumerate(farm["tiles"][0]):
            t["fed_today"] = True
            t["cared_today"] = index in selected if day == 0 else True
        game._daily_refresh_animals(farm, day)
        if day in (5, 7):
            name = "SHEEP" if day == 5 else "COW"
            first_yields[name] = [t["yield_units"] for t in farm["tiles"][0] if t["animal"] == name]
    assert first_yields == {"SHEEP": [6, 6], "COW": [6, 6]}


def test_current_production_care_counts_toward_next_cycle_only():
    from kaggle_environments.envs.kaggriculture import kaggriculture as game

    sheep = tile("SHEEP")
    sheep["pending_care_bonus"] = 5
    assert care_priority(sheep, 5, animal_data(game, "SHEEP")) == 60
    farm = {"tiles": [[sheep]]}
    sheep["cared_today"] = True
    game._daily_refresh_animals(farm, 5)
    assert sheep["yield_units"] == 6
    assert sheep["pending_care_bonus"] == 1


def test_care_has_no_value_after_last_effective_day():
    from kaggle_environments.envs.kaggriculture import kaggriculture as game

    for name in game.ANIMALS:
        assert care_priority(tile(name), 28, animal_data(game, name)) == 0
