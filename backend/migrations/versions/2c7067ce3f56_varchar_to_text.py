"""varchar to text

Revision ID: 2c7067ce3f56
Revises: 0e56afa1e4b6
Create Date: 2026-06-04

NOTE: The initial migration (0e56afa1e4b6) was first applied to the shared
Supabase DB with varchar columns; this migration corrected those columns to
text and was stamped into that DB's chain. The committed copy of the initial
migration was later cleaned to create the columns as ``sa.Text()`` directly,
so on a *fresh* database this migration is a near no-op (it only rebuilds the
search_vector generated column + GIN index). Do NOT delete or squash it:
``alembic_version`` on the live DB references this revision and removing it
would break ``alembic upgrade``/``downgrade`` there.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "2c7067ce3f56"
down_revision: str | None = "0e56afa1e4b6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_TEXT = sa.Text()
_VARCHAR = sa.String()

_ADD_SEARCH_VECTOR = """
    ALTER TABLE medication_registry
      ADD COLUMN search_vector tsvector
      GENERATED ALWAYS AS (
        to_tsvector('simple',
          coalesce(name, '') || ' ' || coalesce(active_ingredient, ''))
      ) STORED
"""
_ADD_GIN_INDEX = """
    CREATE INDEX ix_medication_registry_search_vector
      ON medication_registry USING GIN (search_vector)
"""


def upgrade() -> None:
    op.alter_column("users", "email", type_=_TEXT)

    # Drop generated column + index before altering dependent columns
    op.execute("DROP INDEX IF EXISTS ix_medication_registry_search_vector")
    op.execute("ALTER TABLE medication_registry DROP COLUMN IF EXISTS search_vector")

    for col in [
        "name",
        "active_ingredient",
        "producer",
        "route_of_administration",
        "leaflet_url",
        "specification_url",
    ]:
        op.alter_column("medication_registry", col, type_=_TEXT)

    op.execute(_ADD_SEARCH_VECTOR)
    op.execute(_ADD_GIN_INDEX)

    op.alter_column("cabinet_entries", "dosage_period", type_=_TEXT)


def downgrade() -> None:
    op.alter_column("cabinet_entries", "dosage_period", type_=_VARCHAR)

    op.execute("DROP INDEX IF EXISTS ix_medication_registry_search_vector")
    op.execute("ALTER TABLE medication_registry DROP COLUMN IF EXISTS search_vector")

    for col in [
        "name",
        "active_ingredient",
        "producer",
        "route_of_administration",
        "leaflet_url",
        "specification_url",
    ]:
        op.alter_column("medication_registry", col, type_=_VARCHAR)

    op.execute(_ADD_SEARCH_VECTOR)
    op.execute(_ADD_GIN_INDEX)

    op.alter_column("users", "email", type_=_VARCHAR)
