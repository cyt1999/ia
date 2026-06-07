from types import SimpleNamespace

from app.channels.feishu.channel import FeishuChannel
from app.config.settings import Settings
from app.services.message_renderer import MessageRenderer


class FakeSdkChannel:
    def __init__(self) -> None:
        self.sent = []

    async def send(self, chat_id, payload):
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

