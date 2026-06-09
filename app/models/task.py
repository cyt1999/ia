from datetime import date, datetime, time

from sqlalchemy import Date, DateTime, ForeignKey, Integer, String, Text, Time
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base
from app.utils.timezone import now_utc


class Task(Base):
    __tablename__ = "tasks"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    title: Mapped[str] = mapped_column(String(255))
    description: Mapped[str | None] = mapped_column(Text)
    importance: Mapped[str] = mapped_column(String(32), default="medium")
    task_type: Mapped[str] = mapped_column(String(32), default="work")
    planned_date: Mapped[date | None] = mapped_column(Date)
    planned_time: Mapped[time | None] = mapped_column(Time)
    estimated_minutes: Mapped[int | None] = mapped_column(Integer)
    recurrence_rule: Mapped[str | None] = mapped_column(String(32))
    action_key: Mapped[str | None] = mapped_column(String(64))
    actual_completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(32), default="not_started", index=True)
    reminder_window_min: Mapped[int] = mapped_column(Integer, default=10)
    reminder_window_max: Mapped[int] = mapped_column(Integer, default=30)
    requires_confirmation: Mapped[bool] = mapped_column(default=True)
    source: Mapped[str] = mapped_column(String(32), default="user")
    notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=now_utc, onupdate=now_utc
    )
