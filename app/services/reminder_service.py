import random
from datetime import date, datetime, time, timedelta

from sqlalchemy import and_, select
from sqlalchemy.orm import Session

from app.channels.base import NotificationChannel
from app.models.enums import ReminderKind, ReminderStatus, TaskStatus
from app.models.reminder import Reminder
from app.models.task import Task
from app.services.message_renderer import MessageRenderer
from app.services.scheduled_action_service import ScheduledActionExecutor
from app.utils.timezone import combine_local, from_utc, sleep_midnight_for, to_utc


class ReminderService:
    def __init__(
        self,
        db: Session,
        renderer: MessageRenderer | None = None,
        randomizer: random.Random | None = None,
    ) -> None:
        self.db = db
        self.renderer = renderer or MessageRenderer()
        self.randomizer = randomizer or random.Random()

    def generate_default_day(self, *, user_id: int, day: date, timezone: str) -> list[Reminder]:
        specs = [
            (ReminderKind.WORK_START, "开始工作", time(9, 0), True),
            (ReminderKind.REST_START, "午休", time(12, 0), True),
            (ReminderKind.WORK_START, "下午工作", time(13, 30), True),
            (ReminderKind.WORK_END, "结束工作", time(18, 0), True),
            (ReminderKind.REVIEW, "晚间复盘", time(23, 0), True),
            (ReminderKind.SLEEP_PREP, "睡觉准备", time(23, 30), True),
        ]
        reminders: list[Reminder] = []
        for kind, title, start_time, needs_pre_notice in specs:
            start = combine_local(day, start_time, timezone)
            reminders.append(self._build_reminder(user_id, kind, title, start, needs_pre_notice))
        sleep_start = sleep_midnight_for(day, timezone)
        reminders.append(
            self._build_reminder(user_id, ReminderKind.SLEEP, "睡觉", sleep_start, True)
        )
        self.db.add_all(reminders)
        self.db.commit()
        return reminders

    def create_for_task(
        self,
        *,
        user_id: int,
        task_id: int,
        title: str,
        planned_date: date | None,
        planned_time: time | None,
        timezone: str,
    ) -> Reminder | None:
        if planned_date is None or planned_time is None:
            return None

        start = combine_local(planned_date, planned_time, timezone)
        reminder = Reminder(
            user_id=user_id,
            task_id=task_id,
            kind=ReminderKind.TASK.value,
            title=title,
            scheduled_start_at=to_utc(start),
            reminder_at=to_utc(start),
        )
        self.db.add(reminder)
        self.db.commit()
        self.db.refresh(reminder)
        return reminder

    def reschedule_for_task(self, *, task: Task, timezone: str) -> Reminder | None:
        for reminder in self.db.scalars(
            select(Reminder).where(
                and_(
                    Reminder.task_id == task.id,
                    Reminder.status.in_(
                        [ReminderStatus.PENDING.value, ReminderStatus.SNOOZED.value]
                    ),
                )
            )
        ):
            reminder.status = ReminderStatus.CANCELLED.value
            reminder.next_retry_at = None
        self.db.commit()
        return self.create_for_task(
            user_id=task.user_id,
            task_id=task.id,
            title=task.title,
            planned_date=task.planned_date,
            planned_time=task.planned_time,
            timezone=timezone,
        )

    async def send_due(
        self,
        *,
        channel: NotificationChannel,
        chat_id: str,
        now: datetime,
        timezone: str = "Asia/Shanghai",
    ) -> int:
        due = list(
            self.db.scalars(
                select(Reminder).where(
                    and_(
                        Reminder.status.in_(
                            [ReminderStatus.PENDING.value, ReminderStatus.SNOOZED.value]
                        ),
                        Reminder.reminder_at <= now,
                    )
                )
            )
        )
        sent = 0
        for reminder in due:
            message = self._message_for_reminder(reminder, now=now, timezone=timezone)
            result = await channel.send(chat_id, message)
            if result.ok:
                reminder.status = ReminderStatus.SENT.value
                reminder.next_retry_at = now + timedelta(minutes=10)
                self._schedule_next_recurring_task_reminder(reminder, timezone)
                sent += 1
        self.db.commit()
        return sent

    def _message_for_reminder(
        self, reminder: Reminder, *, now: datetime, timezone: str
    ):
        task = self.db.get(Task, reminder.task_id) if reminder.task_id else None
        if task and task.action_key:
            message = ScheduledActionExecutor(self.db, self.renderer).message_for(
                action_key=task.action_key,
                user_id=reminder.user_id,
                now=now,
                timezone=timezone,
                reminder_id=reminder.id,
                task_id=reminder.task_id,
            )
            if message is not None:
                return message

        body = "差不多该切换状态了。先做最小一步就行。"
        return self.renderer.reminder(
            title=reminder.title,
            planned_at=reminder.scheduled_start_at,
            body=body,
            reminder_id=reminder.id,
            task_id=reminder.task_id,
        )

    def ack(self, reminder_id: int) -> Reminder | None:
        reminder = self.db.get(Reminder, reminder_id)
        if reminder is None:
            return None
        reminder.status = ReminderStatus.ACKED.value
        reminder.next_retry_at = None
        self.db.commit()
        return reminder

    def snooze(self, reminder_id: int, minutes: int, now: datetime) -> Reminder | None:
        reminder = self.db.get(Reminder, reminder_id)
        if reminder is None:
            return None
        reminder.status = ReminderStatus.SNOOZED.value
        reminder.reminder_at = now + timedelta(minutes=minutes)
        reminder.next_retry_at = None
        self.db.commit()
        return reminder

    def retry_due(self, now: datetime) -> list[Reminder]:
        due = list(
            self.db.scalars(
                select(Reminder).where(
                    and_(
                        Reminder.status == ReminderStatus.SENT.value,
                        Reminder.next_retry_at <= now,
                    )
                )
            )
        )
        for reminder in due:
            if reminder.retry_count >= reminder.max_retries:
                reminder.status = ReminderStatus.EXHAUSTED.value
                reminder.next_retry_at = None
            else:
                reminder.retry_count += 1
                reminder.next_retry_at = now + timedelta(minutes=10)
        self.db.commit()
        return due

    def _build_reminder(
        self,
        user_id: int,
        kind: ReminderKind,
        title: str,
        start: datetime,
        needs_pre_notice: bool,
    ) -> Reminder:
        offset = self.randomizer.randint(10, 30) if needs_pre_notice else 0
        reminder_at = start - timedelta(minutes=offset)
        return Reminder(
            user_id=user_id,
            kind=kind.value,
            title=title,
            scheduled_start_at=to_utc(start),
            reminder_at=to_utc(reminder_at),
        )

    def _schedule_next_recurring_task_reminder(
        self, reminder: Reminder, timezone: str
    ) -> None:
        if reminder.task_id is None:
            return
        task = self.db.get(Task, reminder.task_id)
        if (
            task is None
            or task.recurrence_rule is None
            or task.status not in {TaskStatus.NOT_STARTED.value, TaskStatus.IN_PROGRESS.value}
            or task.planned_time is None
        ):
            return

        current_start = from_utc(reminder.scheduled_start_at, timezone)
        next_day = self._next_recurrence_date(current_start.date(), task.recurrence_rule)
        next_start = combine_local(next_day, task.planned_time, timezone)
        task.planned_date = next_day
        self.db.add(
            Reminder(
                user_id=task.user_id,
                task_id=task.id,
                kind=ReminderKind.TASK.value,
                title=task.title,
                scheduled_start_at=to_utc(next_start),
                reminder_at=to_utc(next_start),
            )
        )

    def _next_recurrence_date(self, current_day: date, recurrence_rule: str) -> date:
        next_day = current_day + timedelta(days=1)
        if recurrence_rule != "weekdays":
            return next_day
        while next_day.weekday() >= 5:
            next_day += timedelta(days=1)
        return next_day
