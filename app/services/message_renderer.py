from datetime import datetime

from app.channels.actions import default_reminder_actions, default_review_actions
from app.channels.messages import MessageField, OutboundMessage


class MessageRenderer:
    def reminder(
        self,
        *,
        title: str,
        planned_at: datetime,
        body: str,
        importance: str | None = None,
        reminder_id: int | None = None,
        task_id: int | None = None,
    ) -> OutboundMessage:
        fields = [MessageField(label="计划时间", value=planned_at.strftime("%H:%M"))]
        if importance:
            fields.append(MessageField(label="重要程度", value=importance))
        plain = f"{title}\n计划时间：{planned_at:%H:%M}\n{body}"
        return OutboundMessage(
            title=title,
            body=body,
            fields=fields,
            actions=default_reminder_actions(reminder_id),
            plain_text=plain,
            importance=importance,
            related_task_id=task_id,
            related_reminder_id=reminder_id,
        )

    def task_list(
        self,
        *,
        title: str,
        rows: list[str],
        body: str = "",
        empty_text: str = "今天还没有安排。",
    ) -> OutboundMessage:
        content = "\n".join(rows) if rows else empty_text
        plain = f"{title}\n\n{content}"
        if body:
            plain = f"{plain}\n\n{body}"
        return OutboundMessage(title=title, body=body or content, plain_text=plain)

    def review_prompt(self, *, body: str, missed_notes: list[str] | None = None) -> OutboundMessage:
        fields = []
        if missed_notes:
            fields.append(MessageField(label="未回应提醒", value="；".join(missed_notes)))
        plain = f"晚间复盘\n\n{body}"
        return OutboundMessage(
            title="晚间复盘",
            body=body,
            fields=fields,
            actions=default_review_actions(),
            plain_text=plain,
        )

    def text(self, *, title: str, body: str) -> OutboundMessage:
        return OutboundMessage(title=title, body=body, plain_text=body)
