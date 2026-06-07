from app.channels.base import InboundInteraction
from app.config.settings import Settings
from app.services.authz_service import AuthzService


def test_authz_accepts_configured_user_and_chat() -> None:
    settings = Settings(
        FEISHU_ALLOWED_OPEN_ID="ou_user",
        FEISHU_ALLOWED_CHAT_ID="oc_chat",
    )
    interaction = InboundInteraction(
        channel="feishu",
        message_id="m1",
        sender_id="ou_user",
        chat_id="oc_chat",
    )

    assert AuthzService(settings).is_allowed(interaction)


def test_authz_rejects_unconfigured_user() -> None:
    settings = Settings(FEISHU_ALLOWED_OPEN_ID="ou_user")
    interaction = InboundInteraction(channel="feishu", message_id="m1", sender_id="other")

    assert not AuthzService(settings).is_allowed(interaction)

