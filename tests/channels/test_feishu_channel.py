from types import SimpleNamespace

from app.channels.feishu.channel import FeishuChannel
from app.config.settings import Settings
from app.services.message_renderer import MessageRenderer


class FakeSdkChannel:
    def __init__(self, *, error: Exception | None = None) -> None:
        self.sent = []
        self.error = error

    async def send(self, chat_id, payload):
        if self.error:
            raise self.error
        self.sent.append((chat_id, payload))
        return SimpleNamespace(success=True, message_id="om_1", error=None)


async def test_feishu_channel_sends_interactive_message_through_sdk() -> None:
    sdk_channel = FakeSdkChannel()
    channel = FeishuChannel(Settings(FEISHU_APP_ID="cli", FEISHU_APP_SECRET="secret"), sdk_channel)
    message = MessageRenderer().review_prompt(body="今天完成了什么？")

    result = await channel.send("oc_chat", message)

    assert result.ok
    assert result.provider_message_id == "om_1"
    assert sdk_channel.sent[0][0] == "oc_chat"
    assert "card" in sdk_channel.sent[0][1]


async def test_feishu_channel_falls_back_when_injected_channel_fails() -> None:
    primary = FakeSdkChannel(error=TimeoutError("primary timeout"))
    fallback = FakeSdkChannel()
    channel = FeishuChannel(
        Settings(FEISHU_APP_ID="cli", FEISHU_APP_SECRET="secret"),
        sdk_channel=primary,
        fallback_sdk_channel=fallback,
    )
    message = MessageRenderer().text(title="已安排", body="我已安排「客户报价」。")

    result = await channel.send("oc_chat", message)

    assert result.ok
    assert result.provider_message_id == "om_1"
    assert primary.sent == []
    assert fallback.sent[0][0] == "oc_chat"
    assert fallback.sent[0][1]["text"] == "我已安排「客户报价」。"
