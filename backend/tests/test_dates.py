from datetime import datetime

from app.services.dates import day_bounds


def test_day_bounds_uses_london_daylight_saving_time():
    start, end = day_bounds("2026-08-09")
    assert start == datetime(2026, 8, 8, 23, 0, 0)
    assert end == datetime(2026, 8, 9, 23, 0, 0)
