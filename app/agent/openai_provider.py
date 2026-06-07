import json

from openai import AsyncOpenAI
from pydantic import ValidationError

from app.agent.intents import IntentType, ParsedIntent
from app.config.settings import Settings
from app.schemas.reviews import ReviewParsedUpdate

AI_UNAVAILABLE_MESSAGE = "当前小助手失联了，请稍后再试。"


class OpenAIProvider:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.client = (
            AsyncOpenAI(api_key=settings.openai_api_key) if settings.openai_api_key else None
        )

    async def parse_intent(self, *, user_id: int, text: str, timezone: str) -> ParsedIntent:
        if self.client is None:
            return unavailable_intent()
        try:
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
        except Exception:
            return unavailable_intent()
        try:
            return ParsedIntent.model_validate_json(raw)
        except ValidationError:
            return unavailable_intent()

    async def parse_review(self, *, text: str) -> ReviewParsedUpdate:
        if self.client is None:
            return unavailable_review_update()
        try:
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
        except Exception:
            return unavailable_review_update()

    async def reminder_copy(self, *, title: str, kind: str, context: str | None = None) -> str:
        if self.client is None:
            return _default_reminder_copy(title=title, kind=kind)
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


def unavailable_intent() -> ParsedIntent:
    return ParsedIntent(
        intent=IntentType.UNKNOWN,
        reply=AI_UNAVAILABLE_MESSAGE,
        confidence=0.0,
    )


def unavailable_review_update() -> ReviewParsedUpdate:
    return ReviewParsedUpdate(state_note=AI_UNAVAILABLE_MESSAGE)


def _default_reminder_copy(*, title: str, kind: str) -> str:
    if kind in {"rest_start", "work_end"}:
        return "到休息时间了。现在不用解释进度，先把自己放下来。"
    if kind in {"sleep_prep", "sleep"}:
        return "准备收尾啦，今天不用再硬撑。"
    return f"差不多该开始：{title}。先做最小一步就行。"
