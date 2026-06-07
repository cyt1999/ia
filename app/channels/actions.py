from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class ActionId(StrEnum):
    ACK_REMINDER = "ack_reminder"
    SNOOZE_REMINDER = "snooze_reminder"
    SKIP_TODAY = "skip_today"
    START_REVIEW = "start_review"
    REVIEW_LATER = "review_later"
    SKIP_REVIEW = "skip_review"


class MessageAction(BaseModel):
    id: ActionId
    label: str
    payload: dict[str, Any] = Field(default_factory=dict)


def default_reminder_actions(reminder_id: int | None = None) -> list[MessageAction]:
    payload = {"reminder_id": reminder_id} if reminder_id is not None else {}
    return [
        MessageAction(id=ActionId.ACK_REMINDER, label="知道了", payload=payload),
        MessageAction(
            id=ActionId.SNOOZE_REMINDER,
            label="推迟 10 分钟",
            payload={**payload, "minutes": 10},
        ),
        MessageAction(
            id=ActionId.SNOOZE_REMINDER,
            label="推迟 30 分钟",
            payload={**payload, "minutes": 30},
        ),
        MessageAction(id=ActionId.SKIP_TODAY, label="今天不做了", payload=payload),
    ]


def default_review_actions() -> list[MessageAction]:
    return [
        MessageAction(id=ActionId.START_REVIEW, label="开始复盘"),
        MessageAction(id=ActionId.REVIEW_LATER, label="稍后提醒", payload={"minutes": 30}),
        MessageAction(id=ActionId.SKIP_REVIEW, label="今天跳过"),
    ]

