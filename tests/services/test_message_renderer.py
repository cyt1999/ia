from datetime import UTC, datetime

from app.channels.actions import ActionId
from app.services.message_renderer import MessageRenderer


def test_reminder_message_has_plain_text_and_actions() -> None:
    message = MessageRenderer().reminder(
        title="准备开始：客户报价",
        planned_at=datetime(2026, 6, 7, 1, 0, tzinfo=UTC),
        body="先打开文件。",
        importance="high",
        reminder_id=12,
    )

    assert message.plain_text
    assert message.actions[0].id == ActionId.ACK_REMINDER
    assert message.actions[0].payload["reminder_id"] == 12
    assert all("feishu" not in action.model_dump_json().lower() for action in message.actions)


def test_task_list_empty_fallback() -> None:
    message = MessageRenderer().task_list(title="今天安排", rows=[])

    assert "今天还没有安排" in message.plain_text

