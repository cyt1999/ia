from enum import StrEnum

from pydantic import BaseModel, Field

from app.schemas.goals import GoalCreate, GoalProgressUpdate
from app.schemas.tasks import TaskCreate


class IntentType(StrEnum):
    CREATE_TASK = "create_task"
    LIST_TASKS = "list_tasks"
    CREATE_GOAL = "create_goal"
    UPDATE_GOAL_PROGRESS = "update_goal_progress"
    LIST_GOALS = "list_goals"
    GOAL_STATUS = "goal_status"
    REMEMBER = "remember"
    COMPLETE_TASK = "complete_task"
    POSTPONE_TASK = "postpone_task"
    CANCEL_TASK = "cancel_task"
    ACKNOWLEDGE = "acknowledge"
    SMALL_TALK = "small_talk"
    UNKNOWN = "unknown"


class ParsedIntent(BaseModel):
    intent: IntentType
    task: TaskCreate | None = None
    goal: GoalCreate | None = None
    goal_progress: GoalProgressUpdate | None = None
    target_title: str | None = None
    memory: str | None = None
    reply: str | None = None
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
