from datetime import date

from pydantic import BaseModel, Field


class ReviewParsedUpdate(BaseModel):
    completed_task_titles: list[str] = Field(default_factory=list)
    postponed_task_titles: list[str] = Field(default_factory=list)
    cancelled_task_titles: list[str] = Field(default_factory=list)
    tomorrow_tasks: list[str] = Field(default_factory=list)
    completed_summary: str | None = None
    unfinished_summary: str | None = None
    tomorrow_plan: str | None = None
    state_note: str | None = None


class ReviewCreate(BaseModel):
    user_id: int
    review_date: date
    raw_response: str
    parsed: ReviewParsedUpdate
    missed_reminder_notes: str | None = None

