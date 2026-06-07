from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base
from app.utils.timezone import now_utc


class InboundMessage(Base):
    __tablename__ = "inbound_messages"
    __table_args__ = (UniqueConstraint("channel", "channel_message_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), index=True)
    channel: Mapped[str] = mapped_column(String(32), default="feishu")
    channel_message_id: Mapped[str] = mapped_column(String(255))
    sender_id: Mapped[str | None] = mapped_column(String(255))
    chat_id: Mapped[str | None] = mapped_column(String(255))
    text: Mapped[str | None] = mapped_column(Text)
    action_id: Mapped[str | None] = mapped_column(String(128))
    action_payload: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(32), default="received")
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)
