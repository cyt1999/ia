from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base
from app.utils.timezone import now_utc


class NotificationAttempt(Base):
    __tablename__ = "notification_attempts"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    reminder_id: Mapped[int | None] = mapped_column(ForeignKey("reminders.id"), index=True)
    review_id: Mapped[int | None] = mapped_column(ForeignKey("reviews.id"), index=True)
    channel: Mapped[str] = mapped_column(String(32), default="feishu")
    provider_message_id: Mapped[str | None] = mapped_column(String(255))
    status: Mapped[str] = mapped_column(String(32))
    error_summary: Mapped[str | None] = mapped_column(Text)
    sent_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)
