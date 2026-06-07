import json

from app.agent.deepseek_provider import AI_UNAVAILABLE_MESSAGE, DeepSeekProvider
from app.agent.intents import IntentType
from app.config.settings import Settings


async def test_no_deepseek_key_returns_unavailable_intent() -> None:
    provider = DeepSeekProvider(Settings(DEEPSEEK_API_KEY=""))

    parsed = await provider.parse_intent(
        user_id=1,
        text="明天上午做一下客户报价，比较重要，9 点开始，大概 2 小时。",
        timezone="Asia/Shanghai",
    )

    assert parsed.intent == IntentType.UNKNOWN
    assert parsed.reply == AI_UNAVAILABLE_MESSAGE
    assert parsed.task is None


async def test_deepseek_json_output_intent_is_used() -> None:
    provider = DeepSeekProvider(
        Settings(
            DEEPSEEK_API_KEY="test-key",
            DEEPSEEK_MODEL="deepseek-v4-pro",
            DEEPSEEK_REASONING_EFFORT="high",
            DEEPSEEK_THINKING_ENABLED=True,
        )
    )
    provider.client = FakeDeepSeekClient(
        output={
            "intent": "create_task",
            "task": {
                "user_id": 1,
                "title": "客户报价",
                "importance": "high",
                "task_type": "work",
                "planned_date": "2026-06-08",
                "planned_time": "09:00:00",
                "estimated_minutes": 120,
                "source": "user",
                "notes": None,
            },
            "target_title": None,
            "reply": None,
            "confidence": 0.92,
        }
    )

    parsed = await provider.parse_intent(
        user_id=1,
        text="明天上午 9 点做客户报价，比较重要，大概 2 小时。",
        timezone="Asia/Shanghai",
    )

    kwargs = provider.client.chat.completions.last_kwargs
    assert parsed.intent == IntentType.CREATE_TASK
    assert parsed.task is not None
    assert parsed.task.title == "客户报价"
    assert parsed.task.planned_time.hour == 9
    assert kwargs["model"] == "deepseek-v4-pro"
    assert kwargs["response_format"] == {"type": "json_object"}
    assert kwargs["reasoning_effort"] == "high"
    assert kwargs["extra_body"] == {"thinking": {"type": "enabled"}}
    assert "json" in kwargs["messages"][0]["content"].lower()
    assert "EXAMPLE JSON OUTPUT" in kwargs["messages"][0]["content"]


async def test_deepseek_json_output_review_is_used() -> None:
    provider = DeepSeekProvider(Settings(DEEPSEEK_API_KEY="test-key"))
    provider.client = FakeDeepSeekClient(
        output={
            "completed_task_titles": ["客户报价"],
            "postponed_task_titles": [],
            "cancelled_task_titles": [],
            "tomorrow_tasks": ["整理方案"],
            "completed_summary": "完成了客户报价。",
            "unfinished_summary": None,
            "tomorrow_plan": "继续整理方案。",
            "state_note": "状态还可以。",
        }
    )

    parsed = await provider.parse_review(text="今天完成客户报价，明天整理方案。")

    kwargs = provider.client.chat.completions.last_kwargs
    assert parsed.completed_task_titles == ["客户报价"]
    assert parsed.tomorrow_tasks == ["整理方案"]
    assert kwargs["response_format"] == {"type": "json_object"}
    assert "review_update" in kwargs["messages"][0]["content"]


class FakeDeepSeekClient:
    def __init__(self, *, output: dict | str) -> None:
        self.chat = FakeChat(output=output)


class FakeChat:
    def __init__(self, *, output: dict | str) -> None:
        self.completions = FakeCompletions(output=output)


class FakeCompletions:
    def __init__(self, *, output: dict | str) -> None:
        self.output = output
        self.last_kwargs = {}

    async def create(self, **kwargs):
        self.last_kwargs = kwargs
        output_text = self.output if isinstance(self.output, str) else json.dumps(self.output)
        return FakeResponse(content=output_text)


class FakeResponse:
    def __init__(self, *, content: str) -> None:
        self.choices = [FakeChoice(content=content)]


class FakeChoice:
    def __init__(self, *, content: str) -> None:
        self.message = FakeMessage(content=content)


class FakeMessage:
    def __init__(self, *, content: str) -> None:
        self.content = content
