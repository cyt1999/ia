from datetime import datetime

from sqlalchemy import DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base
from app.utils.timezone import now_utc


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    feishu_open_id: Mapped[str | None] = mapped_column(String(128), unique=True)
    feishu_chat_id: Mapped[str | None] = mapped_column(String(128), unique=True)
    timezone: Mapped[str] = mapped_column(String(64), default="Asia/Shanghai")
    style_preference: Mapped[str] = mapped_column(String(64), default="playful")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=now_utc, onupdate=now_utc
    )
