import json

from app.agent.intents import IntentType
from app.agent.openai_provider import AI_UNAVAILABLE_MESSAGE, OpenAIProvider
from app.config.settings import Settings


async def test_no_api_key_returns_unavailable_intent() -> None:
    provider = OpenAIProvider(Settings(OPENAI_API_KEY=""))

    parsed = await provider.parse_intent(
        user_id=1,
        text="明天上午做一下客户报价，比较重要，9 点开始，大概 2 小时。",
        timezone="Asia/Shanghai",
    )

    assert parsed.intent == IntentType.UNKNOWN
    assert parsed.reply == AI_UNAVAILABLE_MESSAGE
    assert parsed.task is None


async def test_responses_api_structured_intent_output_is_used() -> None:
    provider = OpenAIProvider(Settings(OPENAI_API_KEY="test-key"))
    provider.client = FakeOpenAIClient(
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

    assert parsed.intent == IntentType.CREATE_TASK
    assert parsed.task is not None
    assert parsed.task.title == "客户报价"
    assert parsed.task.planned_time.hour == 9
    assert provider.client.responses.last_kwargs["text"]["format"]["type"] == "json_schema"
    assert provider.client.responses.last_kwargs["text"]["format"]["name"] == "parsed_intent"


async def test_responses_api_structured_review_output_is_used() -> None:
    provider = OpenAIProvider(Settings(OPENAI_API_KEY="test-key"))
    provider.client = FakeOpenAIClient(
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

    assert parsed.completed_task_titles == ["客户报价"]
    assert parsed.tomorrow_tasks == ["整理方案"]
    assert provider.client.responses.last_kwargs["text"]["format"]["type"] == "json_schema"
    assert provider.client.responses.last_kwargs["text"]["format"]["name"] == "review_update"


class FakeOpenAIClient:
    def __init__(self, *, output: dict) -> None:
        self.responses = FakeResponses(output=output)


class FakeResponses:
    def __init__(self, *, output: dict) -> None:
        self.output = output
        self.last_kwargs = {}

    async def create(self, **kwargs):
        self.last_kwargs = kwargs
        return FakeResponse(output_text=json.dumps(self.output, ensure_ascii=False))


class FakeResponse:
    def __init__(self, *, output_text: str) -> None:
        self.output_text = output_text
