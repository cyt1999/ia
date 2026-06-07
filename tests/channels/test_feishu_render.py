from datetime import UTC, datetime

from app.channels.feishu.render import render_message
from app.services.message_renderer import MessageRenderer


def test_reminder_renders_interactive_card() -> None:
    message = MessageRenderer().reminder(
        title="开始工作",
        planned_at=datetime(2026, 6, 7, 1, 0, tzinfo=UTC),
        body="先做最小一步。",
        reminder_id=1,
    )

    msg_type, content = render_message(message)

    assert msg_type == "interactive"
    assert content["header"]["title"]["content"] == "开始工作"
    assert content["_fallback_text"]
    assert content["elements"][-1]["actions"][0]["value"]["action_id"] == "ack_reminder"

