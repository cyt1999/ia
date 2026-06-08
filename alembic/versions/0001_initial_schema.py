"""initial schema

Revision ID: 0001
Revises:
Create Date: 2026-06-06
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("feishu_open_id", sa.String(length=128), unique=True),
        sa.Column("feishu_chat_id", sa.String(length=128), unique=True),
        sa.Column("timezone", sa.String(length=64), nullable=False),
        sa.Column("style_preference", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "tasks",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text()),
        sa.Column("importance", sa.String(length=32), nullable=False),
        sa.Column("task_type", sa.String(length=32), nullable=False),
        sa.Column("planned_date", sa.Date()),
        sa.Column("planned_time", sa.Time()),
        sa.Column("estimated_minutes", sa.Integer()),
        sa.Column("recurrence_rule", sa.String(length=32)),
        sa.Column("actual_completed_at", sa.DateTime(timezone=True)),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("reminder_window_min", sa.Integer(), nullable=False),
        sa.Column("reminder_window_max", sa.Integer(), nullable=False),
        sa.Column("requires_confirmation", sa.Boolean(), nullable=False),
        sa.Column("source", sa.String(length=32), nullable=False),
        sa.Column("notes", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_tasks_user_id", "tasks", ["user_id"])
    op.create_index("ix_tasks_status", "tasks", ["status"])
    op.create_table(
        "reviews",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("review_date", sa.Date(), nullable=False),
        sa.Column("completed_summary", sa.Text()),
        sa.Column("unfinished_summary", sa.Text()),
        sa.Column("tomorrow_plan", sa.Text()),
        sa.Column("state_note", sa.Text()),
        sa.Column("missed_reminder_notes", sa.Text()),
        sa.Column("raw_response", sa.Text()),
        sa.Column("structured_output", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_reviews_user_id", "reviews", ["user_id"])
    op.create_index("ix_reviews_review_date", "reviews", ["review_date"])
    op.create_table(
        "reminders",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("task_id", sa.Integer(), sa.ForeignKey("tasks.id")),
        sa.Column("kind", sa.String(length=32), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("scheduled_start_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("reminder_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("next_retry_at", sa.DateTime(timezone=True)),
        sa.Column("retry_count", sa.Integer(), nullable=False),
        sa.Column("max_retries", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("quiet_override", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_reminders_user_id", "reminders", ["user_id"])
    op.create_index("ix_reminders_task_id", "reminders", ["task_id"])
    op.create_index("ix_reminders_kind", "reminders", ["kind"])
    op.create_index("ix_reminders_status", "reminders", ["status"])
    op.create_index("ix_reminders_reminder_at", "reminders", ["reminder_at"])
    op.create_index("ix_reminders_next_retry_at", "reminders", ["next_retry_at"])
    op.create_table(
        "notification_attempts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("reminder_id", sa.Integer(), sa.ForeignKey("reminders.id")),
        sa.Column("review_id", sa.Integer(), sa.ForeignKey("reviews.id")),
        sa.Column("channel", sa.String(length=32), nullable=False),
        sa.Column("provider_message_id", sa.String(length=255)),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("error_summary", sa.Text()),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_notification_attempts_user_id", "notification_attempts", ["user_id"])
    op.create_index(
        "ix_notification_attempts_reminder_id", "notification_attempts", ["reminder_id"]
    )
    op.create_index("ix_notification_attempts_review_id", "notification_attempts", ["review_id"])
    op.create_table(
        "inbound_messages",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id")),
        sa.Column("channel", sa.String(length=32), nullable=False),
        sa.Column("channel_message_id", sa.String(length=255), nullable=False),
        sa.Column("sender_id", sa.String(length=255)),
        sa.Column("chat_id", sa.String(length=255)),
        sa.Column("text", sa.Text()),
        sa.Column("action_id", sa.String(length=128)),
        sa.Column("action_payload", sa.Text()),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("received_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("channel", "channel_message_id"),
    )
    op.create_index("ix_inbound_messages_user_id", "inbound_messages", ["user_id"])


def downgrade() -> None:
    op.drop_table("inbound_messages")
    op.drop_table("notification_attempts")
    op.drop_table("reminders")
    op.drop_table("reviews")
    op.drop_table("tasks")
    op.drop_table("users")
