import json
import re
from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

from openai import AsyncOpenAI
from pydantic import ValidationError

from app.agent.intents import IntentType, ParsedIntent
from app.config.settings import Settings
from app.models.enums import Importance
from app.schemas.reviews import ReviewParsedUpdate
from app.schemas.tasks import TaskCreate


class OpenAIProvider:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.client = (
            AsyncOpenAI(api_key=settings.openai_api_key) if settings.openai_api_key else None
        )

    async def parse_intent(self, *, user_id: int, text: str, timezone: str) -> ParsedIntent:
        if self.client is None:
            return _fallback_intent(user_id=user_id, text=text, timezone=timezone)
        response = await self.client.responses.create(
            model=self.settings.openai_model,
            input=[
                {
                    "role": "system",
                    "content": (
                        "Parse the user's Chinese assistant message into JSON. "
                        "Return fields: intent, target_title, reply, confidence. "
                        "Use intent values create_task, complete_task, postpone_task, "
                        "cancel_task, acknowledge, small_talk, unknown."
                    ),
                },
                {"role": "user", "content": text},
            ],
        )
        raw = response.output_text
        try:
            return ParsedIntent.model_validate_json(raw)
        except ValidationError:
            return ParsedIntent(
                intent=IntentType.UNKNOWN,
                reply="我有点没理解，你可以换个说法吗？",
                confidence=0.0,
            )

    async def parse_review(self, *, text: str) -> ReviewParsedUpdate:
        if self.client is None:
            return ReviewParsedUpdate(
                completed_summary=text,
                unfinished_summary=None,
                tomorrow_plan=None,
            )
        response = await self.client.responses.create(
            model=self.settings.openai_model,
            input=[
                {
                    "role": "system",
                    "content": (
                        "Extract an evening review into JSON matching fields: "
                        "completed_task_titles, postponed_task_titles, cancelled_task_titles, "
                        "tomorrow_tasks, completed_summary, unfinished_summary, tomorrow_plan, "
                        "state_note."
                    ),
                },
                {"role": "user", "content": text},
            ],
        )
        return ReviewParsedUpdate.model_validate(json.loads(response.output_text))

    async def reminder_copy(self, *, title: str, kind: str, context: str | None = None) -> str:
        if self.client is None:
            return _fallback_copy(title=title, kind=kind)
        response = await self.client.responses.create(
            model=self.settings.openai_model,
            input=[
                {
                    "role": "system",
                    "content": "Write one short encouraging Chinese reminder. No lecture.",
                },
                {"role": "user", "content": f"kind={kind}, title={title}, context={context or ''}"},
            ],
        )
        return response.output_text.strip()


def _fallback_intent(*, user_id: int, text: str, timezone: str) -> ParsedIntent:
    normalized = text.strip().lower()
    if normalized in {"知道了", "收到", "ok", "好的"}:
        return ParsedIntent(intent=IntentType.ACKNOWLEDGE, confidence=1.0)
    if "做完" in normalized or "完成" in normalized:
        return ParsedIntent(intent=IntentType.COMPLETE_TASK, confidence=0.8)
    if "不做" in normalized or "取消" in normalized:
        return ParsedIntent(intent=IntentType.CANCEL_TASK, confidence=0.8)
    if "推迟" in normalized or "改到明天" in normalized:
        return ParsedIntent(intent=IntentType.POSTPONE_TASK, confidence=0.8)
    if "做" in normalized or "任务" in normalized or "安排" in normalized:
        task = _parse_task(user_id=user_id, text=text, timezone=timezone)
        if task:
            return ParsedIntent(intent=IntentType.CREATE_TASK, task=task, confidence=0.7)
    return ParsedIntent(intent=IntentType.SMALL_TALK, reply="我收到了。", confidence=0.4)


def _parse_task(*, user_id: int, text: str, timezone: str) -> TaskCreate | None:
    title_match = re.search(r"(?:做|处理|完成|推进)(一下)?(?P<title>[^，,。\.]+)", text)
    if not title_match:
        return None
    title = title_match.group("title").strip()
    title = re.sub(
        r"(比较重要|很重要|重要|大概.*|预计.*|[0-9一二两三四五六七八九十]+ ?小时).*",
        "",
        title,
    ).strip()
    if not title:
        return None

    today = datetime.now(ZoneInfo(timezone)).date()
    planned_date = today + timedelta(days=1) if "明天" in text else today
    planned_time = _parse_time(text)
    importance = Importance.HIGH if "重要" in text else Importance.MEDIUM
    estimated_minutes = _parse_duration(text)
    return TaskCreate(
        user_id=user_id,
        title=title,
        importance=importance,
        planned_date=planned_date,
        planned_time=planned_time,
        estimated_minutes=estimated_minutes,
    )


def _parse_time(text: str) -> time | None:
    match = re.search(r"(?P<hour>\d{1,2})\s*[点:：](?P<minute>\d{1,2})?", text)
    if not match:
        if "上午" in text:
            return time(9, 0)
        if "下午" in text:
            return time(13, 30)
        return None
    hour = int(match.group("hour"))
    minute = int(match.group("minute") or 0)
    if "下午" in text and hour < 12:
        hour += 12
    return time(hour, minute)


def _parse_duration(text: str) -> int | None:
    match = re.search(r"(?:大概|预计)?\s*(?P<hours>\d+(?:\.\d+)?)\s*小时", text)
    if not match:
        return None
    return int(float(match.group("hours")) * 60)


def _fallback_copy(*, title: str, kind: str) -> str:
    if kind in {"rest_start", "work_end"}:
        return "到休息时间了。现在不用解释进度，先把自己放下来。"
    if kind in {"sleep_prep", "sleep"}:
        return "准备收尾啦，今天不用再硬撑。"
    return f"差不多该开始：{title}。先做最小一步就行。"
