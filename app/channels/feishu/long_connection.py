import asyncio
import json
from collections.abc import Callable
from threading import Thread

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
        self._thread: Thread | None = None
        self._start_error: BaseException | None = None
        self._register_handlers()

    async def start(self) -> None:
        self._thread = Thread(
            target=self._run_sdk_channel,
            name="feishu-long-connection",
            daemon=True,
        )
        self._thread.start()
        await asyncio.sleep(0.5)
        if self._start_error is not None:
            raise self._start_error
        self.logger.info("feishu_long_connection_starting")

    async def stop(self) -> None:
        await self.sdk_channel.disconnect()
        self.logger.info("feishu_long_connection_stopped")

    def _register_handlers(self) -> None:
        self.sdk_channel.on("message", self._on_message)
        self.sdk_channel.on("cardAction", self._on_card_action)
        self.sdk_channel.on("error", self._on_error)

    def _run_sdk_channel(self) -> None:
        try:
            self.sdk_channel.start()
        except BaseException as exc:
            self._start_error = exc
            self.logger.error("feishu_long_connection_start_failed", error=str(exc))

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
