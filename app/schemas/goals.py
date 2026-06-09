from datetime import date

from pydantic import BaseModel

from app.models.enums import GoalDirection, GoalProgressKind


class GoalCreate(BaseModel):
    user_id: int
    title: str
    metric_name: str
    unit: str
    direction: GoalDirection
    baseline_value: float | None = None
    current_value: float | None = None
    target_value: float | None = None
    target_delta: float | None = None
    start_date: date | None = None
    deadline: date | None = None
    notes: str | None = None


class GoalProgressUpdate(BaseModel):
    goal_title: str | None = None
    kind: GoalProgressKind
    value: float
    note: str | None = None
    raw_text: str | None = None
