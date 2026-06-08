import json
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

from openai import AsyncOpenAI
from pydantic import ValidationError

from app.agent.intents import IntentType, ParsedIntent
from app.config.settings import Settings
from app.schemas.reviews import ReviewParsedUpdate
from app.services.memory_service import MemoryService

AI_UNAVAILABLE_MESSAGE = "当前小助手失联了，请稍后再试。"


class DeepSeekProvider:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.client = (
            AsyncOpenAI(
                api_key=settings.deepseek_api_key,
                base_url=settings.deepseek_base_url,
                timeout=settings.deepseek_timeout_seconds,
            )
            if settings.deepseek_api_key
            else None
        )
        self.memory = MemoryService(settings)

    async def parse_intent(self, *, user_id: int, text: str, timezone: str) -> ParsedIntent:
        if self.client is None:
            return unavailable_intent()
        try:
            local_now = datetime.now(ZoneInfo(timezone))
            prompt = (
                f"user_id={user_id}\n"
                f"timezone={timezone}\n"
                f"now={local_now.isoformat()}\n"
                f"today={local_now.date().isoformat()}\n"
                f"user_message={text}"
            )
            raw = await self._structured_json(
                name="parsed_intent",
                instructions=_INTENT_INSTRUCTIONS,
                user_input=prompt,
                schema=_PARSED_INTENT_SCHEMA,
                memory=self.memory.read(),
            )
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
            raw = await self._structured_json(
                name="review_update",
                instructions=_REVIEW_INSTRUCTIONS,
                user_input=text,
                schema=_REVIEW_UPDATE_SCHEMA,
                memory=self.memory.read(),
            )
            return ReviewParsedUpdate.model_validate(json.loads(raw))
        except Exception:
            return unavailable_review_update()

    async def reminder_copy(self, *, title: str, kind: str, context: str | None = None) -> str:
        if self.client is None:
            return _default_reminder_copy(title=title, kind=kind)
        memory = self.memory.read()
        user_input = f"kind={kind}, title={title}, context={context or ''}"
        system = "Write one short encouraging Chinese reminder. No lecture."
        if memory:
            system = f"{system}\n\n长期记忆：\n{memory}"
        response = await self.client.chat.completions.create(
            **self._chat_completion_kwargs(
                messages=[
                    {
                        "role": "system",
                        "content": system,
                    },
                    {"role": "user", "content": user_input},
                ],
            )
        )
        return (response.choices[0].message.content or "").strip()

    async def _structured_json(
        self,
        *,
        name: str,
        instructions: str,
        user_input: str,
        schema: dict[str, Any],
        memory: str = "",
    ) -> str:
        response = await self.client.chat.completions.create(
            **self._chat_completion_kwargs(
                messages=[
                    {
                        "role": "system",
                        "content": _chat_json_instructions(
                            instructions=instructions,
                            name=name,
                            schema=schema,
                            memory=memory,
                        ),
                    },
                    {"role": "user", "content": user_input},
                ],
                response_format={"type": "json_object"},
            )
        )
        return response.choices[0].message.content or ""

    def _chat_completion_kwargs(
        self,
        *,
        messages: list[dict[str, str]],
        response_format: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        kwargs: dict[str, Any] = {
            "model": self.settings.deepseek_model,
            "messages": messages,
            "stream": False,
            "max_tokens": self.settings.deepseek_max_tokens,
        }
        if response_format is not None:
            kwargs["response_format"] = response_format
        kwargs["reasoning_effort"] = self.settings.deepseek_reasoning_effort
        if self.settings.deepseek_thinking_enabled:
            kwargs["extra_body"] = {"thinking": {"type": "enabled"}}
        return kwargs


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


def _chat_json_instructions(
    *,
    instructions: str,
    name: str,
    schema: dict[str, Any],
    memory: str = "",
) -> str:
    memory_block = f"\n\n长期记忆：\n{memory}" if memory else ""
    return (
        f"{instructions}{memory_block}\n\n"
        "你必须只输出一个 JSON 对象，不要输出 Markdown，不要输出代码块。"
        f"输出名称：{name}\n"
        f"JSON Schema：{json.dumps(schema, ensure_ascii=False)}\n"
        f"EXAMPLE JSON OUTPUT：{_json_example(name)}"
    )


def _json_example(name: str) -> str:
    if name == "review_update":
        return json.dumps(
            {
                "completed_task_titles": ["客户报价"],
                "postponed_task_titles": [],
                "cancelled_task_titles": [],
                "tomorrow_tasks": ["整理方案"],
                "completed_summary": "完成了客户报价。",
                "unfinished_summary": None,
                "tomorrow_plan": "明天整理方案。",
                "state_note": "状态还可以。",
            },
            ensure_ascii=False,
        )
    return json.dumps(
        {
            "intent": "create_task",
            "task": {
                "user_id": 1,
                "title": "客户报价",
                "importance": "high",
                "task_type": "work",
                "planned_date": "2026-06-08",
                "planned_time": "09:00:00",
                "estimated_minutes": 120,
                "recurrence_rule": None,
                "source": "user",
                "notes": None,
            },
            "target_title": None,
            "memory": None,
            "reply": None,
            "confidence": 0.92,
        },
        ensure_ascii=False,
    )


_INTENT_INSTRUCTIONS = """
你是一个个人任务助手的意图解析器。你只输出符合 JSON Schema 的 JSON。

根据用户中文消息判断 intent：
- create_task：用户要新增任务、安排事项、提醒未来要做的事
- list_tasks：用户要查看当前任务、今天任务、待办事项或问“有哪些任务”
- remember：用户只是在表达一个需要长期保存的偏好、固定习惯、背景信息或助手行为规则
- complete_task：用户表示完成了某个任务
- postpone_task：用户要推迟任务
- cancel_task：用户要取消/不做任务
- acknowledge：用户确认收到提醒
- small_talk：用户只是聊天、吐槽、表达状态
- unknown：无法确定

创建任务时：
- task 必须是对象；其他 intent 时 task 必须是 null
- task.user_id 使用输入里的 user_id
- task.title 是用户真正要做的事，用短名词/动宾短语，不要照抄整句话
- task.title 不要包含“提醒我、提醒、去、哦、哈”等请求包装或语气词
- 例：“明天10点提醒我去健身哦” 的 title 是“健身”，不是“去健身”
- 例：“等会12点提醒我吃饭哈” 的 title 是“吃饭”，不是“吃饭提醒”
- planned_date 使用 YYYY-MM-DD，planned_time 使用 HH:MM:SS；没有明确日期或时间就填 null
- “今天、明天、后天、下周”等相对日期必须基于输入里的 today 计算
- recurrence_rule 表示重复规则：一次性任务填 null；“每天”填 daily；“每个工作日/工作日”填 weekdays
- 周期任务的 planned_date 是下一次发生日期
- 如果今天对应时间已经早于输入里的 now，就填下一个符合规则的日期
- importance 只能是 high、medium、low；默认 medium
- task_type 只能是 work、life、rest、sleep、review、temp_reminder；默认 work
- source 使用 user
- target_title 用于完成、推迟、取消任务时匹配任务标题；没有就填 null
- memory 可在任何 intent 中填写，但只记录长期稳定偏好、固定习惯、用户背景或助手行为规则
- 不要把一次性任务、一次性提醒、短期状态、普通聊天、完整原文写进 memory；不确定就填 null
- 用户纠正助手行为时，应把纠正提炼成简短 memory，例如“任务名应提炼真正要做的事”
- reply 可以给一条自然、简短、不机械的中文回应；创建/修改类可以填 null，让服务层生成确认文案
- list_tasks 时 task 必须是 null，reply 可以填 null，让服务层从数据库生成任务列表
- remember 只用于没有其他任务操作、主要是在表达长期偏好的消息；task 必须是 null
""".strip()


_REVIEW_INSTRUCTIONS = """
你是一个晚间复盘解析器。你只输出符合 JSON Schema 的 JSON。
从用户复盘里提取完成内容、未完成内容、明日计划和状态备注。
无法提取的文本字段填 null，列表字段填空数组。
""".strip()


_NULLABLE_STRING = {"type": ["string", "null"]}
_NULLABLE_INTEGER = {"type": ["integer", "null"]}
_NULLABLE_RECURRENCE_RULE = {"type": ["string", "null"], "enum": ["daily", "weekdays", None]}

_TASK_SCHEMA: dict[str, Any] = {
    "type": ["object", "null"],
    "additionalProperties": False,
    "properties": {
        "user_id": {"type": "integer"},
        "title": {"type": "string"},
        "importance": {"type": "string", "enum": ["high", "medium", "low"]},
        "task_type": {
            "type": "string",
            "enum": ["work", "life", "rest", "sleep", "review", "temp_reminder"],
        },
        "planned_date": _NULLABLE_STRING,
        "planned_time": _NULLABLE_STRING,
        "estimated_minutes": _NULLABLE_INTEGER,
        "recurrence_rule": _NULLABLE_RECURRENCE_RULE,
        "source": {"type": "string", "enum": ["user", "review", "carry_over", "system"]},
        "notes": _NULLABLE_STRING,
    },
    "required": [
        "user_id",
        "title",
        "importance",
        "task_type",
        "planned_date",
        "planned_time",
        "estimated_minutes",
        "recurrence_rule",
        "source",
        "notes",
    ],
}

_PARSED_INTENT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "intent": {
            "type": "string",
            "enum": [
                "create_task",
                "list_tasks",
                "remember",
                "complete_task",
                "postpone_task",
                "cancel_task",
                "acknowledge",
                "small_talk",
                "unknown",
            ],
        },
        "task": _TASK_SCHEMA,
        "target_title": _NULLABLE_STRING,
        "memory": _NULLABLE_STRING,
        "reply": _NULLABLE_STRING,
        "confidence": {"type": "number", "minimum": 0.0, "maximum": 1.0},
    },
    "required": ["intent", "task", "target_title", "memory", "reply", "confidence"],
}

_REVIEW_UPDATE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "completed_task_titles": {"type": "array", "items": {"type": "string"}},
        "postponed_task_titles": {"type": "array", "items": {"type": "string"}},
        "cancelled_task_titles": {"type": "array", "items": {"type": "string"}},
        "tomorrow_tasks": {"type": "array", "items": {"type": "string"}},
        "completed_summary": _NULLABLE_STRING,
        "unfinished_summary": _NULLABLE_STRING,
        "tomorrow_plan": _NULLABLE_STRING,
        "state_note": _NULLABLE_STRING,
    },
    "required": [
        "completed_task_titles",
        "postponed_task_titles",
        "cancelled_task_titles",
        "tomorrow_tasks",
        "completed_summary",
        "unfinished_summary",
        "tomorrow_plan",
        "state_note",
    ],
}
