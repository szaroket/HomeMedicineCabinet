"""initial schema

Revision ID: 0e56afa1e4b6
Revises:
Create Date: 2026-06-04

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0e56afa1e4b6"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("email", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_users_email"), "users", ["email"], unique=True)

    op.create_table(
        "medication_registry",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("active_ingredient", sa.Text(), nullable=True),
        sa.Column("tablet_count", sa.Integer(), nullable=True),
        sa.Column("producer", sa.Text(), nullable=True),
        sa.Column("route_of_administration", sa.Text(), nullable=True),
        sa.Column("leaflet_url", sa.Text(), nullable=True),
        sa.Column("specification_url", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_medication_registry_name"),
        "medication_registry",
        ["name"],
        unique=False,
    )

    op.execute(
        """
        ALTER TABLE medication_registry
          ADD COLUMN search_vector tsvector
          GENERATED ALWAYS AS (
            to_tsvector('simple',
              coalesce(name, '') || ' ' || coalesce(active_ingredient, ''))
          ) STORED
        """
    )
    op.execute(
        """
        CREATE INDEX ix_medication_registry_search_vector
          ON medication_registry USING GIN (search_vector)
        """
    )

    op.create_table(
        "user_preferences",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("expiry_threshold_days", sa.Integer(), nullable=False),
        sa.Column("close_to_finish_threshold_days", sa.Integer(), nullable=False),
        sa.Column("min_package_count", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id"),
    )

    op.create_table(
        "cabinet_entries",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("medication_registry_id", sa.Uuid(), nullable=False),
        sa.Column("package_count", sa.Integer(), nullable=False),
        sa.Column("partial_tablet_count", sa.Integer(), nullable=True),
        sa.Column("expiry_date", sa.Date(), nullable=False),
        sa.Column("is_important", sa.Boolean(), nullable=False),
        sa.Column("is_used", sa.Boolean(), nullable=False),
        sa.Column("dosage_times", sa.Integer(), nullable=True),
        sa.Column("dosage_period", sa.Text(), nullable=True),
        sa.Column("dosage_amount", sa.Integer(), nullable=True),
        sa.Column("dosage_start_date", sa.Date(), nullable=True),
        sa.Column("dosage_end_date", sa.Date(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["medication_registry_id"], ["medication_registry.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "user_id",
            "medication_registry_id",
            "expiry_date",
            name="uq_cabinet_entries_user_med_expiry",
        ),
    )

    op.execute(
        """
        ALTER TABLE cabinet_entries
          ADD CONSTRAINT ck_cabinet_entries_package_count_non_negative
          CHECK (package_count >= 0)
        """
    )
    op.execute(
        """
        ALTER TABLE cabinet_entries
          ADD CONSTRAINT ck_cabinet_entries_dosage_period
          CHECK (dosage_period IN ('day', 'week'))
        """
    )


def downgrade() -> None:
    op.execute(
        "ALTER TABLE cabinet_entries DROP CONSTRAINT IF EXISTS ck_cabinet_entries_dosage_period"
    )
    op.execute(
        "ALTER TABLE cabinet_entries DROP CONSTRAINT IF EXISTS ck_cabinet_entries_package_count_non_negative"
    )
    op.drop_table("cabinet_entries")
    op.drop_table("user_preferences")
    op.execute("DROP INDEX IF EXISTS ix_medication_registry_search_vector")
    op.drop_index(op.f("ix_medication_registry_name"), table_name="medication_registry")
    op.drop_table("medication_registry")
    op.drop_index(op.f("ix_users_email"), table_name="users")
    op.drop_table("users")
