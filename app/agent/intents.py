from enum import StrEnum

from pydantic import BaseModel, Field

from app.schemas.tasks import TaskCreate


class IntentType(StrEnum):
    CREATE_TASK = "create_task"
    LIST_TASKS = "list_tasks"
    COMPLETE_TASK = "complete_task"
    POSTPONE_TASK = "postpone_task"
    CANCEL_TASK = "cancel_task"
    ACKNOWLEDGE = "acknowledge"
    SMALL_TALK = "small_talk"
    UNKNOWN = "unknown"


class ParsedIntent(BaseModel):
    intent: IntentType
    task: TaskCreate | None = None
    target_title: str | None = None
    reply: str | None = None
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
