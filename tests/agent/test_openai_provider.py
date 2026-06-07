from app.agent.intents import IntentType
from app.agent.openai_provider import OpenAIProvider
from app.config.settings import Settings


async def test_fallback_parses_chinese_task_creation() -> None:
    provider = OpenAIProvider(Settings(OPENAI_API_KEY=""))

    parsed = await provider.parse_intent(
        user_id=1,
        text="明天上午做一下客户报价，比较重要，9 点开始，大概 2 小时。",
        timezone="Asia/Shanghai",
    )

    assert parsed.intent == IntentType.CREATE_TASK
    assert parsed.task is not None
    assert parsed.task.title == "客户报价"
    assert parsed.task.importance == "high"
    assert parsed.task.planned_time.hour == 9
    assert parsed.task.estimated_minutes == 120

