"""Cabinet database operations."""

import logging
import uuid
from datetime import date, timedelta

from sqlalchemy import func, select, text
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlmodel import col
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.cabinet.models import CabinetEntry
from app.api.v1.medicines.models import MedicationRegistry
from app.db.connector import persist
from app.utilities.errors import CabinetDatabaseError

logger = logging.getLogger("app.cabinet.crud")


async def get_registry_by_id(
    session: AsyncSession,
    registry_id: uuid.UUID,
) -> MedicationRegistry | None:
    """Fetch a single MedicationRegistry row by primary key.

    Args:
        session: Active async database session.
        registry_id: UUID of the registry row.

    Returns:
        The MedicationRegistry instance, or None if not found.

    Raises:
        CabinetDatabaseError: If the database query fails.
    """
    try:
        result = await session.execute(
            select(MedicationRegistry).where(col(MedicationRegistry.id) == registry_id)
        )
    except SQLAlchemyError as exc:
        logger.error(
            "Failed to fetch registry row %s: %s", registry_id, exc, exc_info=True
        )
        raise CabinetDatabaseError() from exc
    return result.scalar_one_or_none()


async def find_entry(
    session: AsyncSession,
    user_id: uuid.UUID,
    registry_id: uuid.UUID,
    expiry_date: date,
) -> CabinetEntry | None:
    """Look up an existing cabinet entry by the dedup key.

    The dedup key is (user_id, medication_registry_id, expiry_date), which is
    also the unique constraint on the table.

    Args:
        session: Active async database session.
        user_id: UUID of the authenticated user.
        registry_id: UUID of the medication registry row.
        expiry_date: Expiry date of the entry.

    Returns:
        The CabinetEntry if found, otherwise None.

    Raises:
        CabinetDatabaseError: If the database query fails.
    """
    try:
        result = await session.execute(
            select(CabinetEntry).where(
                col(CabinetEntry.user_id) == user_id,
                col(CabinetEntry.medication_registry_id) == registry_id,
                col(CabinetEntry.expiry_date) == expiry_date,
            )
        )
    except SQLAlchemyError as exc:
        logger.error("Failed to look up cabinet entry: %s", exc, exc_info=True)
        raise CabinetDatabaseError() from exc
    return result.scalar_one_or_none()


async def insert_entry(
    session: AsyncSession,
    user_id: uuid.UUID,
    registry_id: uuid.UUID,
    package_count: int,
    partial_tablet_count: int | None,
    expiry_date: date,
) -> CabinetEntry:
    """Insert a new cabinet entry and flush to obtain its ID.

    Args:
        session: Active async database session.
        user_id: UUID of the authenticated user.
        registry_id: UUID of the medication registry row.
        package_count: Number of packages.
        partial_tablet_count: Tablets in the last (partial) package, or None.
        expiry_date: Expiry date for the entry.

    Returns:
        The newly created CabinetEntry (committed).

    Raises:
        IntegrityError: On a duplicate-key violation (concurrent add); propagated
            untouched for the service-layer race guard to handle.
        CabinetDatabaseError: If the insert, flush, or commit fails for any other
            database reason.
    """
    entry = CabinetEntry(
        user_id=user_id,
        medication_registry_id=registry_id,
        package_count=package_count,
        partial_tablet_count=partial_tablet_count,
        expiry_date=expiry_date,
    )
    try:
        async with persist(session, entry):
            session.add(entry)
    except IntegrityError:
        # Duplicate-key (concurrent add) must reach the service-layer race guard
        # untouched so it can roll back, re-read, and merge (FR-010).
        raise
    except SQLAlchemyError as exc:
        logger.error("Failed to insert cabinet entry: %s", exc, exc_info=True)
        raise CabinetDatabaseError() from exc
    return entry


def _build_base_query(
    user_id: uuid.UUID,
    today: date,
    threshold: int,
    status: str | None,
    tsquery: str | None,
):
    """Build the filtered join query (no ORDER BY / LIMIT / OFFSET).

    Args:
        user_id: UUID of the authenticated user.
        today: Reference date for status computation.
        threshold: Expiry threshold in days.
        status: Optional status filter ("valid", "expiring", "expired").
        tsquery: Optional safe prefix tsquery string for full-text search.

    Returns:
        A SQLAlchemy select construct with all WHERE clauses applied.
    """
    stmt = (
        select(CabinetEntry, MedicationRegistry)
        .join(
            MedicationRegistry,
            col(CabinetEntry.medication_registry_id) == col(MedicationRegistry.id),
        )
        .where(col(CabinetEntry.user_id) == user_id)
    )
    if status == "expired":
        stmt = stmt.where(col(CabinetEntry.expiry_date) < today)
    elif status == "expiring":
        stmt = stmt.where(
            col(CabinetEntry.expiry_date) >= today,
            col(CabinetEntry.expiry_date) <= today + timedelta(days=threshold),
        )
    elif status == "valid":
        stmt = stmt.where(
            col(CabinetEntry.expiry_date) > today + timedelta(days=threshold)
        )
    if tsquery is not None:
        stmt = stmt.where(
            text(
                "medication_registry.search_vector @@ to_tsquery('simple', :tsquery)"
            ).bindparams(tsquery=tsquery)
        )
    return stmt


async def list_entries(
    session: AsyncSession,
    user_id: uuid.UUID,
    today: date,
    threshold: int,
    status: str | None,
    tsquery: str | None,
    order: str,
    limit: int,
    offset: int,
) -> tuple[list[tuple[CabinetEntry, MedicationRegistry]], int]:
    """Fetch a filtered, sorted, paginated page of cabinet entries plus total count.

    Args:
        session: Active async database session.
        user_id: UUID of the authenticated user.
        today: Reference date for status SQL predicates.
        threshold: Expiry threshold days for status SQL predicates.
        status: Optional status filter ("valid", "expiring", "expired").
        tsquery: Optional safe prefix tsquery string for full-text search.
        order: Sort direction for medication name ("asc" or "desc").
        limit: Page size.
        offset: Row offset for pagination.

    Returns:
        Tuple of (page rows, total count under the same filters).

    Raises:
        CabinetDatabaseError: If any database query fails.
    """
    base = _build_base_query(user_id, today, threshold, status, tsquery)

    name_col = func.lower(col(MedicationRegistry.name))
    order_clause = name_col.asc() if order == "asc" else name_col.desc()

    page_q = (
        base.order_by(order_clause, col(CabinetEntry.id).asc())
        .limit(limit)
        .offset(offset)
    )

    count_q = select(func.count()).select_from(
        _build_base_query(user_id, today, threshold, status, tsquery).subquery()
    )

    try:
        page_result = await session.execute(page_q)
    except SQLAlchemyError as exc:
        logger.error(
            "Failed to list cabinet entries for user %s: %s",
            user_id,
            exc,
            exc_info=True,
        )
        raise CabinetDatabaseError() from exc

    try:
        count_result = await session.execute(count_q)
    except SQLAlchemyError as exc:
        logger.error(
            "Failed to count cabinet entries for user %s: %s",
            user_id,
            exc,
            exc_info=True,
        )
        raise CabinetDatabaseError() from exc

    rows = list(page_result.tuples().all())
    total = count_result.scalar_one()
    return rows, total


async def update_entry_counts(
    session: AsyncSession,
    entry: CabinetEntry,
    package_count: int,
    partial_tablet_count: int | None,
) -> CabinetEntry:
    """Update the package and partial-tablet counts of an existing entry.

    Args:
        session: Active async database session.
        entry: The CabinetEntry to update.
        package_count: New package count.
        partial_tablet_count: New partial tablet count, or None.

    Returns:
        The updated CabinetEntry (committed).

    Raises:
        CabinetDatabaseError: If the flush or commit fails.
    """
    entry.package_count = package_count
    entry.partial_tablet_count = partial_tablet_count
    try:
        async with persist(session, entry):
            session.add(entry)
    except SQLAlchemyError as exc:
        logger.error(
            "Failed to update cabinet entry %s: %s", entry.id, exc, exc_info=True
        )
        raise CabinetDatabaseError() from exc
    return entry
