from app.channels.base import SendResult
from app.channels.feishu.client import build_lark_channel
from app.channels.feishu.render import render_message
from app.channels.messages import OutboundMessage
from app.config.settings import Settings


class FeishuChannel:
    def __init__(self, settings: Settings, sdk_channel=None) -> None:
        self.sdk_channel = sdk_channel or build_lark_channel(settings)

    async def send(self, chat_id: str, message: OutboundMessage) -> SendResult:
        try:
            msg_type, content = render_message(message)
            payload = {"card": content} if msg_type == "interactive" else {"text": content["text"]}
            result = await self.sdk_channel.send(chat_id, payload)
            return SendResult(
                provider_message_id=getattr(result, "message_id", None),
                ok=getattr(result, "success", True),
                error_summary=str(getattr(result, "error", "") or "") or None,
            )
        except Exception as exc:  # noqa: BLE001
            return SendResult(ok=False, error_summary=str(exc))
