import json
from typing import Any

from app.channels.base import InboundInteraction


def normalize_event(payload: dict[str, Any]) -> InboundInteraction | None:
    event = payload.get("event", payload)
    event_type = payload.get("header", {}).get("event_type") or payload.get("type")

    if event_type == "im.message.receive_v1" or "message" in event:
        message = event.get("message", {})
        sender = event.get("sender", {}).get("sender_id", {})
        content = message.get("content") or "{}"
        try:
            text = json.loads(content).get("text", content)
        except json.JSONDecodeError:
            text = content
        return InboundInteraction(
            channel="feishu",
            message_id=message.get("message_id", ""),
            sender_id=sender.get("open_id"),
            chat_id=message.get("chat_id"),
            text=text,
        )

    action = event.get("action")
    if action:
        value = action.get("value") or {}
        return InboundInteraction(
            channel="feishu",
            message_id=event.get("context", {}).get("open_message_id", ""),
            sender_id=event.get("operator", {}).get("open_id"),
            chat_id=event.get("context", {}).get("open_chat_id"),
            action_id=value.get("action_id"),
            action_payload=value.get("payload") or {},
        )

    return None

