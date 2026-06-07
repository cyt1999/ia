from datetime import date

from app.utils.timezone import sleep_midnight_for, to_utc


def test_sleep_midnight_is_next_day_in_business_timezone() -> None:
    local = sleep_midnight_for(date(2026, 6, 7), "Asia/Shanghai")

    assert local.day == 8
    assert local.hour == 0
    assert to_utc(local).hour == 16

