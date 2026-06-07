from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config.settings import Settings
from app.models.user import User


class UserService:
    def __init__(self, db: Session, settings: Settings) -> None:
        self.db = db
        self.settings = settings

    def current_user(self) -> User:
        stmt = select(User).where(User.feishu_open_id == self.settings.feishu_allowed_open_id)
        user = self.db.scalar(stmt)
        if user:
            return user
        user = User(
            feishu_open_id=self.settings.feishu_allowed_open_id or None,
            feishu_chat_id=self.settings.feishu_allowed_chat_id or None,
            timezone=self.settings.app_timezone,
        )
        self.db.add(user)
        self.db.commit()
        self.db.refresh(user)
        return user

