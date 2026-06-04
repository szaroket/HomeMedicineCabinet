"""reshape medication registry

Revision ID: dc9619b00abd
Revises: 2c7067ce3f56
Create Date: 2026-06-04 19:53:59.753431

Reshapes ``medication_registry`` from the F-02 shape (one lossy ``tablet_count``
plus a single ``producer``) to a package-unit grain that mirrors the official
Polish medicines XML. Column-level only: ``search_vector``, its GIN index,
``name``'s index, and the ``cabinet_entries`` FK are left untouched, so the
generated column is not dropped/recreated and the cabinet schema is undisturbed.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "dc9619b00abd"
down_revision: str | None = "2c7067ce3f56"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_TEXT = sa.Text()

_ADDED_TEXT_COLUMNS = [
    "source_product_id",
    "gtin",
    "strength",
    "pharmaceutical_form",
    "marketing_authorization_holder",
    "manufacturer",
    "atc_code",
    "availability_category",
    "capacity_unit",
]


def upgrade() -> None:
    """Upgrade schema."""
    op.drop_column("medication_registry", "tablet_count")
    op.drop_column("medication_registry", "producer")

    for col in _ADDED_TEXT_COLUMNS:
        op.add_column("medication_registry", sa.Column(col, _TEXT, nullable=True))

    op.add_column(
        "medication_registry", sa.Column("capacity", sa.Numeric(), nullable=True)
    )
    op.add_column(
        "medication_registry",
        sa.Column(
            "is_tablet_based",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("medication_registry", "is_tablet_based")
    op.drop_column("medication_registry", "capacity")

    for col in _ADDED_TEXT_COLUMNS:
        op.drop_column("medication_registry", col)

    op.add_column("medication_registry", sa.Column("producer", _TEXT, nullable=True))
    op.add_column(
        "medication_registry", sa.Column("tablet_count", sa.Integer(), nullable=True)
    )
