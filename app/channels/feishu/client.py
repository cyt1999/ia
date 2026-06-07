from typing import Literal

from lark_oapi.channel import FeishuChannel as LarkFeishuChannel

from app.config.settings import Settings

TransportMode = Literal["ws", "webhook"]


def feishu_transport_mode(value: str) -> TransportMode:
    if value in {"long_connection", "ws", "websocket"}:
        return "ws"
    if value == "webhook":
        return "webhook"
    raise ValueError(f"Unsupported Feishu event mode: {value}")


def build_lark_channel(settings: Settings, *, transport: TransportMode | None = None):
    return LarkFeishuChannel(
        app_id=settings.feishu_app_id,
        app_secret=settings.feishu_app_secret,
        encrypt_key=settings.feishu_encrypt_key or None,
        verification_token=settings.feishu_verification_token or None,
        transport=transport or feishu_transport_mode(settings.feishu_event_mode),
    )
