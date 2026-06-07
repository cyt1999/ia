import json
from collections.abc import Callable

import structlog
from sqlalchemy.orm import Session

from app.channels.base import InboundInteraction
from app.channels.feishu.client import build_lark_channel
from app.config.settings import Settings
from app.db.session import SessionLocal
from app.services.interaction_router import InteractionRouter


class FeishuLongConnectionRunner:
    def __init__(
        self,
        settings: Settings,
        *,
        session_factory: Callable[[], Session] = SessionLocal,
        sdk_channel=None,
    ) -> None:
        self.settings = settings
        self.session_factory = session_factory
        self.sdk_channel = sdk_channel or build_lark_channel(settings, transport="ws")
        self.logger = structlog.get_logger(__name__)
        self._register_handlers()

    async def start(self) -> None:
        await self.sdk_channel.start_background(timeout=30)
        self.logger.info("feishu_long_connection_started")

    async def stop(self) -> None:
        await self.sdk_channel.disconnect()
        self.logger.info("feishu_long_connection_stopped")

    def _register_handlers(self) -> None:
        self.sdk_channel.on("message", self._on_message)
        self.sdk_channel.on("cardAction", self._on_card_action)
        self.sdk_channel.on("error", self._on_error)

    async def _on_message(self, message) -> None:
        interaction = InboundInteraction(
            channel="feishu",
            message_id=message.message_id,
            sender_id=message.sender_id,
            chat_id=message.chat_id,
            text=message.content_text,
        )
        await self._handle(interaction)

    async def _on_card_action(self, event) -> None:
        value = event.action.value or {}
        action_id = value.get("action_id")
        action_payload = value.get("payload") or {}
        dedupe_fragment = json.dumps(value, ensure_ascii=False, sort_keys=True)
        interaction = InboundInteraction(
            channel="feishu",
            message_id=f"{event.message_id}:{event.operator.open_id}:{dedupe_fragment}",
            sender_id=event.operator.open_id,
            chat_id=event.chat_id,
            action_id=action_id,
            action_payload=action_payload,
        )
        await self._handle(interaction)

    async def _on_error(self, error: Exception) -> None:
        self.logger.error("feishu_long_connection_error", error=str(error))

    async def _handle(self, interaction: InboundInteraction) -> None:
        with self.session_factory() as db:
            await InteractionRouter(db=db, settings=self.settings).handle(interaction)
