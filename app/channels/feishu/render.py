import json

from app.channels.messages import OutboundMessage


def render_message(message: OutboundMessage) -> tuple[str, dict]:
    if message.actions:
        return "interactive", _render_card(message)
    return "text", {"text": message.plain_text}


def _render_card(message: OutboundMessage) -> dict:
    elements: list[dict] = [
        {"tag": "markdown", "content": f"**{message.title}**\n\n{message.body}"}
    ]
    if message.fields:
        field_text = "\n".join(f"- **{field.label}**：{field.value}" for field in message.fields)
        elements.append({"tag": "markdown", "content": field_text})
    if message.actions:
        elements.append(
            {
                "tag": "action",
                "actions": [
                    {
                        "tag": "button",
                        "text": {"tag": "plain_text", "content": action.label},
                        "type": "default",
                        "value": {
                            "action_id": action.id.value,
                            "payload": action.payload,
                        },
                    }
                    for action in message.actions
                ],
            }
        )
    return {
        "config": {"wide_screen_mode": True},
        "header": {"title": {"tag": "plain_text", "content": message.title}},
        "elements": elements,
        "_fallback_text": message.plain_text,
        "_debug": json.dumps({"related_reminder_id": message.related_reminder_id}),
    }

