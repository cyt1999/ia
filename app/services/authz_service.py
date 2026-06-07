from app.channels.base import InboundInteraction
from app.config.settings import Settings


class AuthzService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def is_allowed(self, interaction: InboundInteraction) -> bool:
        allowed_open_id = self.settings.feishu_allowed_open_id
        allowed_chat_id = self.settings.feishu_allowed_chat_id
        if allowed_open_id and interaction.sender_id != allowed_open_id:
            return False
        if allowed_chat_id and interaction.chat_id != allowed_chat_id:
            return False
        return True

