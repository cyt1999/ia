from sqlalchemy import and_, select
from sqlalchemy.orm import Session

from app.models.enums import TaskStatus
from app.models.task import Task
from app.schemas.tasks import TaskCreate, TaskSummary
from app.utils.timezone import now_utc


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

    def active_tasks(self, user_id: int) -> list[Task]:
        stmt = select(Task).where(
            and_(
                Task.user_id == user_id,
                Task.status.in_([TaskStatus.NOT_STARTED.value, TaskStatus.IN_PROGRESS.value]),
            )
        )
        return list(self.db.scalars(stmt))

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
            )
            for task in tasks
        ]

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
