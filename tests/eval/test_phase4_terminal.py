"""Terminal calendars retain final-day production and held-product protection."""

from scripts.phase4_terminal import check, production_days


def test_terminal_calendar_against_official_refresh_and_care_order():
    cases = check()
    assert len(cases) == 9
    assert all(row["held_after"] == 3 and row["pending_after"] == 1 for row in cases)


def test_last_sheep_event_is_not_confused_with_current_day():
    from kaggle_environments.envs.kaggriculture import kaggriculture as game

    tile = {"animal": "SHEEP", "placed_day": 2}
    assert production_days(tile, game.ANIMALS, 25) == [26, 29]
    assert production_days(tile, game.ANIMALS, 28) == [29]
    assert production_days(tile, game.ANIMALS, 29) == []


def test_empty_future_calendar_does_not_imply_held_product_is_disposable():
    from kaggle_environments.envs.kaggriculture import kaggriculture as game

    tile = {"animal": "SHEEP", "placed_day": 0, "yield_units": 4}
    assert production_days(tile, game.ANIMALS, 27) == []
    assert tile["yield_units"] > 0
