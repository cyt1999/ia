"""add goals

Revision ID: 0003
Revises: 0002
Create Date: 2026-06-09
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "goals",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("metric_name", sa.String(length=128), nullable=False),
        sa.Column("unit", sa.String(length=32), nullable=False),
        sa.Column("direction", sa.String(length=32), nullable=False),
        sa.Column("baseline_value", sa.Float()),
        sa.Column("current_value", sa.Float()),
        sa.Column("target_value", sa.Float()),
        sa.Column("target_delta", sa.Float()),
        sa.Column("start_date", sa.Date()),
        sa.Column("deadline", sa.Date()),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("notes", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_goals_user_id", "goals", ["user_id"])
    op.create_index("ix_goals_direction", "goals", ["direction"])
    op.create_index("ix_goals_status", "goals", ["status"])
    op.create_table(
        "goal_progress_entries",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("goal_id", sa.Integer(), sa.ForeignKey("goals.id"), nullable=False),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("kind", sa.String(length=32), nullable=False),
        sa.Column("value", sa.Float(), nullable=False),
        sa.Column("note", sa.Text()),
        sa.Column("raw_text", sa.Text()),
        sa.Column("recorded_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_goal_progress_entries_goal_id", "goal_progress_entries", ["goal_id"])
    op.create_index("ix_goal_progress_entries_user_id", "goal_progress_entries", ["user_id"])


def downgrade() -> None:
    op.drop_table("goal_progress_entries")
    op.drop_table("goals")
