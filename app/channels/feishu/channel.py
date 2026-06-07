from app.channels.base import SendResult
from app.channels.feishu.client import FeishuClient
from app.channels.feishu.render import render_message
from app.channels.messages import OutboundMessage


class FeishuChannel:
    def __init__(self, client: FeishuClient) -> None:
        self.client = client

    async def send(self, chat_id: str, message: OutboundMessage) -> SendResult:
        try:
            msg_type, content = render_message(message)
            provider_message_id = await self.client.send_message(chat_id, msg_type, content)
            return SendResult(provider_message_id=provider_message_id)
        except Exception as exc:  # noqa: BLE001
            return SendResult(ok=False, error_summary=str(exc))

