"""add dismissed_notifications

Revision ID: 7726318333b6
Revises: dc9619b00abd
Create Date: 2026-07-07

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "7726318333b6"
down_revision: str | None = "dc9619b00abd"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "dismissed_notifications",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("cabinet_entry_id", sa.Uuid(), nullable=False),
        sa.Column("trigger_type", sa.Text(), nullable=False),
        sa.Column("dismissed_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(
            ["cabinet_entry_id"], ["cabinet_entries.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "user_id",
            "cabinet_entry_id",
            "trigger_type",
            name="uq_dismissed_user_entry_trigger",
        ),
    )
    op.create_index(
        "ix_dismissed_notifications_cabinet_entry_id",
        "dismissed_notifications",
        ["cabinet_entry_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_dismissed_notifications_cabinet_entry_id",
        table_name="dismissed_notifications",
    )
    op.drop_table("dismissed_notifications")
