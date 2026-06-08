import structlog

from app.channels.base import SendResult
from app.channels.feishu.client import build_lark_channel
from app.channels.feishu.render import render_message
from app.channels.messages import OutboundMessage
from app.config.settings import Settings


class FeishuChannel:
    def __init__(self, settings: Settings, sdk_channel=None, fallback_sdk_channel=None) -> None:
        self.settings = settings
        self.sdk_channel = sdk_channel or build_lark_channel(settings)
        self.fallback_sdk_channel = fallback_sdk_channel
        self._has_injected_sdk_channel = sdk_channel is not None
        self.logger = structlog.get_logger(__name__)

    async def send(self, chat_id: str, message: OutboundMessage) -> SendResult:
        msg_type, content = render_message(message)
        payload = {"card": content} if msg_type == "interactive" else {"text": content["text"]}
        primary = await self._send_once(self.sdk_channel, chat_id, payload)
        if primary.ok or not self._has_injected_sdk_channel:
            return primary

        self.logger.warning(
            "feishu_send_primary_failed",
            chat_id=chat_id,
            title=message.title,
            error=primary.error_summary,
        )
        fallback = self.fallback_sdk_channel or build_lark_channel(self.settings)
        secondary = await self._send_once(fallback, chat_id, payload)
        if not secondary.ok and primary.error_summary:
            secondary.error_summary = (
                f"primary={primary.error_summary}; secondary={secondary.error_summary}"
            )
        return secondary

    async def _send_once(self, sdk_channel, chat_id: str, payload: dict) -> SendResult:
        try:
            result = await sdk_channel.send(chat_id, payload)
            return SendResult(
                provider_message_id=getattr(result, "message_id", None),
                ok=getattr(result, "success", True),
                error_summary=str(getattr(result, "error", "") or "") or None,
            )
        except Exception as exc:  # noqa: BLE001
            return SendResult(ok=False, error_summary=str(exc))
