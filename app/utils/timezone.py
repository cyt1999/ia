from datetime import UTC, date, datetime, time, timedelta
from zoneinfo import ZoneInfo


def now_utc() -> datetime:
    return datetime.now(UTC)


def to_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        raise ValueError("datetime must be timezone-aware")
    return value.astimezone(UTC)


def from_utc(value: datetime, timezone: str) -> datetime:
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value.astimezone(ZoneInfo(timezone))


def combine_local(day: date, local_time: time, timezone: str) -> datetime:
    return datetime.combine(day, local_time, ZoneInfo(timezone))


def sleep_midnight_for(day: date, timezone: str) -> datetime:
    return datetime.combine(day + timedelta(days=1), time(0, 0), ZoneInfo(timezone))

