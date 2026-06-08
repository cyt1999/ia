from datetime import date, time

from pydantic import BaseModel

from app.models.enums import Importance, RecurrenceRule, TaskSource, TaskStatus, TaskType


class TaskCreate(BaseModel):
    user_id: int
    title: str
    importance: Importance = Importance.MEDIUM
    task_type: TaskType = TaskType.WORK
    planned_date: date | None = None
    planned_time: time | None = None
    estimated_minutes: int | None = None
    recurrence_rule: RecurrenceRule | None = None
    source: TaskSource = TaskSource.USER
    notes: str | None = None


class TaskSummary(BaseModel):
    id: int
    title: str
    importance: Importance
    task_type: TaskType
    status: TaskStatus
    planned_time: time | None = None
    recurrence_rule: RecurrenceRule | None = None
