from typing import Protocol

from pydantic import BaseModel, Field

from app.channels.messages import OutboundMessage


class InboundInteraction(BaseModel):
    channel: str
    message_id: str
    sender_id: str | None = None
    chat_id: str | None = None
    text: str | None = None
    action_id: str | None = None
    action_payload: dict = Field(default_factory=dict)


class SendResult(BaseModel):
    provider_message_id: str | None = None
    ok: bool = True
    error_summary: str | None = None


class NotificationChannel(Protocol):
    async def send(self, chat_id: str, message: OutboundMessage) -> SendResult:
        ...

