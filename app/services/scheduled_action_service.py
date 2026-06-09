from datetime import datetime

from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session

from app.channels.messages import OutboundMessage
from app.models.enums import TaskActionKey, TaskStatus
from app.models.task import Task
from app.services.goal_service import GoalService
from app.services.message_renderer import MessageRenderer
from app.utils.timezone import combine_local, from_utc, to_utc


class ScheduledActionExecutor:
    def __init__(self, db: Session, renderer: MessageRenderer | None = None) -> None:
        self.db = db
        self.renderer = renderer or MessageRenderer()

    def message_for(
        self,
        *,
        action_key: str,
        user_id: int,
        now: datetime,
        timezone: str,
        reminder_id: int | None = None,
        task_id: int | None = None,
    ) -> OutboundMessage | None:
        if action_key == TaskActionKey.DAILY_BRIEFING.value:
            return self._daily_briefing(
                user_id=user_id,
                now=now,
                timezone=timezone,
                reminder_id=reminder_id,
                task_id=task_id,
            )
        if action_key == TaskActionKey.DAILY_REVIEW.value:
            return self._daily_review(
                user_id=user_id,
                now=now,
                timezone=timezone,
                reminder_id=reminder_id,
                task_id=task_id,
            )
        return None

    def _daily_briefing(
        self,
        *,
        user_id: int,
        now: datetime,
        timezone: str,
        reminder_id: int | None,
        task_id: int | None,
    ) -> OutboundMessage:
        local_today = from_utc(now, timezone).date()
        task_rows = self._today_task_rows(user_id, local_today)
        goal_rows = self._goal_rows(user_id)
        body = "\n".join(
            [
                "任务：",
                *(task_rows or ["- 今天还没有安排。"]),
                "",
                "目标：",
                *(goal_rows or ["- 现在还没有目标。"]),
            ]
        )
        return self._action_message(
            title="今日安排",
            body=body,
            reminder_id=reminder_id,
            task_id=task_id,
        )

    def _daily_review(
        self,
        *,
        user_id: int,
        now: datetime,
        timezone: str,
        reminder_id: int | None,
        task_id: int | None,
    ) -> OutboundMessage:
        local_today = from_utc(now, timezone).date()
        completed_rows = self._completed_task_rows(user_id, local_today, timezone)
        unfinished_rows = self._unfinished_task_rows(user_id, local_today)
        goal_rows = self._goal_rows(user_id)
        body = "\n".join(
            [
                "今天完成：",
                *(completed_rows or ["- 暂时没有记录完成的任务。"]),
                "",
                "仍需关注：",
                *(unfinished_rows or ["- 今天没有未完成任务。"]),
                "",
                "目标：",
                *(goal_rows or ["- 现在还没有目标。"]),
                "",
                "你可以直接回复今天实际做了什么，我会记录复盘。",
            ]
        )
        return self._action_message(
            title="晚间复盘",
            body=body,
            reminder_id=reminder_id,
            task_id=task_id,
        )

    def _today_task_rows(self, user_id: int, local_today) -> list[str]:
        stmt = (
            select(Task)
            .where(
                and_(
                    Task.user_id == user_id,
                    Task.source != "system",
                    Task.status.in_(
                        [TaskStatus.NOT_STARTED.value, TaskStatus.IN_PROGRESS.value]
                    ),
                    or_(Task.planned_date == local_today, Task.planned_date.is_(None)),
                )
            )
            .order_by(Task.planned_time.is_(None), Task.planned_time, Task.id)
        )
        return [self._task_row(task) for task in self.db.scalars(stmt)]

    def _completed_task_rows(self, user_id: int, local_today, timezone: str) -> list[str]:
        start = to_utc(combine_local(local_today, datetime.min.time(), timezone))
        end = to_utc(combine_local(local_today, datetime.max.time(), timezone))
        stmt = (
            select(Task)
            .where(
                and_(
                    Task.user_id == user_id,
                    Task.source != "system",
                    Task.status == TaskStatus.COMPLETED.value,
                    or_(
                        Task.planned_date == local_today,
                        and_(Task.actual_completed_at >= start, Task.actual_completed_at <= end),
                    ),
                )
            )
            .order_by(Task.planned_time.is_(None), Task.planned_time, Task.id)
        )
        return [self._task_row(task) for task in self.db.scalars(stmt)]

    def _unfinished_task_rows(self, user_id: int, local_today) -> list[str]:
        stmt = (
            select(Task)
            .where(
                and_(
                    Task.user_id == user_id,
                    Task.source != "system",
                    Task.status.in_(
                        [TaskStatus.NOT_STARTED.value, TaskStatus.IN_PROGRESS.value]
                    ),
                    Task.planned_date == local_today,
                )
            )
            .order_by(Task.planned_time.is_(None), Task.planned_time, Task.id)
        )
        return [self._task_row(task) for task in self.db.scalars(stmt)]

    def _goal_rows(self, user_id: int) -> list[str]:
        service = GoalService(self.db)
        rows = []
        for goal in service.active_goals(user_id):
            snapshot = service.status_for(goal)
            parts = [snapshot.progress_text]
            if snapshot.percent is not None:
                parts.append(f"完成度 {self._format_number(snapshot.percent)}%")
            if snapshot.remaining_text:
                parts.append(snapshot.remaining_text)
            rows.append(f"- {goal.title}：" + "，".join(parts))
        return rows

    def _task_row(self, task: Task) -> str:
        if task.planned_time:
            return f"- {task.title}（{task.planned_time:%H:%M}）"
        return f"- {task.title}"

    def _action_message(
        self,
        *,
        title: str,
        body: str,
        reminder_id: int | None,
        task_id: int | None,
    ) -> OutboundMessage:
        message = self.renderer.text(title=title, body=body)
        message.related_reminder_id = reminder_id
        message.related_task_id = task_id
        return message

    def _format_number(self, value: float) -> str:
        if value == int(value):
            return str(int(value))
        return f"{value:.1f}".rstrip("0").rstrip(".")
