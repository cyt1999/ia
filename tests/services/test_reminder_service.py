import random
from datetime import UTC, date, datetime, timedelta

from sqlalchemy.orm import Session

from app.models.enums import ReminderStatus
from app.services.reminder_service import ReminderService


def test_generate_default_day_randomizes_pre_notice(db_session: Session, user) -> None:
    service = ReminderService(db_session, randomizer=random.Random(1))

    reminders = service.generate_default_day(
        user_id=user.id,
        day=date(2026, 6, 7),
        timezone="Asia/Shanghai",
    )
    work = reminders[0]
    delta = work.scheduled_start_at - work.reminder_at

    assert timedelta(minutes=10) <= delta <= timedelta(minutes=30)


def test_ack_stops_retry(db_session: Session, user) -> None:
    service = ReminderService(db_session, randomizer=random.Random(1))
    reminder = service.generate_default_day(
        user_id=user.id,
        day=date(2026, 6, 7),
        timezone="Asia/Shanghai",
    )[0]

    acked = service.ack(reminder.id)

    assert acked.status == ReminderStatus.ACKED.value
    assert acked.next_retry_at is None


def test_retry_exhausts_after_max_retries(db_session: Session, user) -> None:
    service = ReminderService(db_session, randomizer=random.Random(1))
    reminder = service.generate_default_day(
        user_id=user.id,
        day=date(2026, 6, 7),
        timezone="Asia/Shanghai",
    )[0]
    now = datetime(2026, 6, 7, 0, 40, tzinfo=UTC)
    reminder.status = ReminderStatus.SENT.value
    reminder.next_retry_at = now
    reminder.retry_count = reminder.max_retries
    db_session.commit()

    service.retry_due(now)

    assert reminder.status == ReminderStatus.EXHAUSTED.value
    assert reminder.next_retry_at is None

