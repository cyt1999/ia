from sqlalchemy import and_, select
from sqlalchemy.orm import Session

from app.models.enums import TaskStatus
from app.models.task import Task
from app.schemas.tasks import TaskCreate, TaskSummary
from app.utils.timezone import from_utc, now_utc


class TaskService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def create_task(self, data: TaskCreate) -> Task:
        task = Task(
            user_id=data.user_id,
            title=data.title,
            importance=data.importance.value,
            task_type=data.task_type.value,
            planned_date=data.planned_date,
            planned_time=data.planned_time,
            estimated_minutes=data.estimated_minutes,
            recurrence_rule=data.recurrence_rule.value if data.recurrence_rule else None,
            action_key=data.action_key.value if data.action_key else None,
            source=data.source.value,
            notes=data.notes,
        )
        self.db.add(task)
        self.db.commit()
        self.db.refresh(task)
        return task

    def today_tasks(self, user_id: int, day) -> list[Task]:
        stmt = (
            select(Task)
            .where(and_(Task.user_id == user_id, Task.planned_date == day))
            .order_by(Task.planned_time.is_(None), Task.planned_time, Task.id)
        )
        return list(self.db.scalars(stmt))

    def active_tasks(self, user_id: int, *, include_system: bool = False) -> list[Task]:
        stmt = select(Task).where(
            and_(
                Task.user_id == user_id,
                Task.status.in_([TaskStatus.NOT_STARTED.value, TaskStatus.IN_PROGRESS.value]),
            )
        )
        if not include_system:
            stmt = stmt.where(Task.source != "system")
        stmt = stmt.order_by(
            Task.planned_date.is_(None),
            Task.planned_date,
            Task.planned_time.is_(None),
            Task.planned_time,
            Task.id,
        )
        return list(self.db.scalars(stmt))

    def current_tasks(
        self, user_id: int, timezone: str, *, include_system: bool = False
    ) -> list[Task]:
        local_now = from_utc(now_utc(), timezone)
        tasks = self.active_tasks(user_id, include_system=include_system)
        return [
            task
            for task in tasks
            if self._is_current_or_future(task, local_now.date(), local_now.time())
        ]

    def complete_most_relevant(self, user_id: int, title: str | None = None) -> Task | None:
        task = self._find_target(user_id, title)
        if task is None:
            return None
        task.status = TaskStatus.COMPLETED.value
        task.actual_completed_at = now_utc()
        self.db.commit()
        self.db.refresh(task)
        return task

    def postpone_most_relevant(self, user_id: int, title: str | None = None) -> Task | None:
        task = self._find_target(user_id, title)
        if task is None:
            return None
        task.status = TaskStatus.POSTPONED.value
        self.db.commit()
        self.db.refresh(task)
        return task

    def cancel_most_relevant(self, user_id: int, title: str | None = None) -> Task | None:
        task = self._find_target(user_id, title)
        if task is None:
            return None
        task.status = TaskStatus.CANCELLED.value
        self.db.commit()
        self.db.refresh(task)
        return task

    def summaries_for(self, tasks: list[Task]) -> list[TaskSummary]:
        return [
            TaskSummary(
                id=task.id,
                title=task.title,
                importance=task.importance,
                task_type=task.task_type,
                status=task.status,
                planned_time=task.planned_time,
                recurrence_rule=task.recurrence_rule,
                action_key=task.action_key,
            )
            for task in tasks
        ]

    def _is_current_or_future(self, task: Task, today, current_time) -> bool:
        if task.planned_date is None:
            return True
        if task.planned_date > today:
            return True
        if task.planned_date < today:
            return False
        if task.planned_time is None:
            return True
        return task.planned_time >= current_time

    def _find_target(self, user_id: int, title: str | None) -> Task | None:
        stmt = select(Task).where(
            and_(
                Task.user_id == user_id,
                Task.status.in_([TaskStatus.NOT_STARTED.value, TaskStatus.IN_PROGRESS.value]),
            )
        )
        if title:
            stmt = stmt.where(Task.title.contains(title))
        stmt = stmt.order_by(
            Task.planned_date.is_(None),
            Task.planned_date,
            Task.planned_time,
            Task.id,
        )
        return self.db.scalar(stmt)
