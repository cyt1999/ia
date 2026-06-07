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
