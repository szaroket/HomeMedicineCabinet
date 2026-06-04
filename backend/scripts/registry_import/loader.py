"""Async batched bulk loader for the medicines registry.

Consumes the parser's row stream and replaces the contents of
``medication_registry`` in a single all-or-none transaction. Re-running is safe:
the table is cleared and reloaded. A guard refuses to wipe the registry while
``cabinet_entries`` references it (which would orphan those FKs) unless ``force``
is passed.
"""

import logging
from collections.abc import Iterable, Iterator
from itertools import batched

import sqlalchemy as sa

from app.api.v1.cabinet.models import CabinetEntry
from app.api.v1.medicines.models import MedicationRegistry
from app.db.connector import async_session_factory

logger = logging.getLogger(__name__)


async def load_registry(
    rows: Iterable[dict], *, batch_size: int = 1000, force: bool = False
) -> int:
    """Replace ``medication_registry`` with ``rows``; return rows inserted.

    The whole operation runs in one transaction: clear the table, insert every
    batch, then a single commit. If any batch fails the transaction rolls back
    and the previous contents are left untouched — never a half-populated table.
    ``DELETE`` (not ``TRUNCATE``) is used because the ``cabinet_entries`` FK
    makes Postgres reject truncating ``medication_registry``.
    """
    insert_stmt = sa.insert(MedicationRegistry)
    inserted = 0
    async with async_session_factory() as session:
        if not force:
            cabinet_rows = await session.scalar(
                sa.select(sa.func.count()).select_from(CabinetEntry)
            )
            if cabinet_rows:
                raise RuntimeError(
                    f"Refusing to reload: cabinet_entries has {cabinet_rows} row(s) "
                    "referencing medication_registry. Clearing the registry would "
                    "orphan those FKs. Re-run with force=True to override."
                )

        await session.execute(sa.delete(MedicationRegistry))
        for batch in _batched_dicts(rows, batch_size):
            # Insert only real columns (the dicts never include the generated
            # search_vector); the uuid PK comes from the model's default.
            await session.execute(insert_stmt, batch)
            inserted += len(batch)
            logger.info("Inserted %d rows so far...", inserted)

        await session.commit()

    return inserted


def _batched_dicts(rows: Iterable[dict], batch_size: int) -> Iterator[list[dict]]:
    """Yield successive lists of at most ``batch_size`` rows."""
    if batch_size < 1:
        raise ValueError("batch_size must be >= 1")
    for batch in batched(rows, batch_size):
        yield list(batch)
