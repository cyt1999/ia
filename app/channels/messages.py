from pydantic import BaseModel, Field

from app.channels.actions import MessageAction


class MessageField(BaseModel):
    label: str
    value: str


class OutboundMessage(BaseModel):
    title: str
    body: str
    fields: list[MessageField] = Field(default_factory=list)
    actions: list[MessageAction] = Field(default_factory=list)
    plain_text: str
    importance: str | None = None
    related_task_id: int | None = None
    related_reminder_id: int | None = None

