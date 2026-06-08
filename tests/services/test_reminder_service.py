import random
from datetime import UTC, date, datetime, timedelta
from types import SimpleNamespace

from sqlalchemy.orm import Session

from app.models.enums import RecurrenceRule, ReminderStatus
from app.models.reminder import Reminder
from app.schemas.tasks import TaskCreate
from app.services.reminder_service import ReminderService
from app.services.task_service import TaskService


class FakeChannel:
    def __init__(self) -> None:
        self.sent = []

    async def send(self, chat_id, message):
        self.sent.append((chat_id, message))
        return SimpleNamespace(ok=True, provider_message_id="reply_1", error_summary=None)


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


async def test_send_due_schedules_next_weekday_recurring_task(
    db_session: Session, user
) -> None:
    task = TaskService(db_session).create_task(
        TaskCreate(
            user_id=user.id,
            title="开始工作",
            planned_date=date(2026, 6, 12),
            planned_time=datetime(2026, 6, 12, 9, 0).time(),
            recurrence_rule=RecurrenceRule.WEEKDAYS,
        )
    )
    service = ReminderService(db_session)
    service.create_for_task(
        user_id=user.id,
        task_id=task.id,
        title=task.title,
        planned_date=task.planned_date,
        planned_time=task.planned_time,
        timezone="Asia/Shanghai",
    )

    sent = await service.send_due(
        channel=FakeChannel(),
        chat_id="oc_chat",
        now=datetime(2026, 6, 12, 1, 0, tzinfo=UTC),
        timezone="Asia/Shanghai",
    )

    reminders = db_session.query(Reminder).order_by(Reminder.id).all()
    assert sent == 1
    assert reminders[0].status == ReminderStatus.SENT.value
    assert reminders[1].scheduled_start_at == datetime(2026, 6, 15, 1, 0)
    assert task.planned_date == date(2026, 6, 15)
