"""Cabinet database operations."""

import logging
import uuid
from datetime import date, timedelta

from sqlalchemy import Float, Integer, case, cast, delete, func, literal, select, text
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlmodel import col
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.cabinet.models import CabinetEntry
from app.api.v1.medicines.models import MedicationRegistry
from app.db.connector import persist
from app.utilities.errors import CabinetDatabaseError
from app.utilities.types import ResolvedUsage

logger = logging.getLogger("app.cabinet.crud")


async def get_registry_by_id(
    session: AsyncSession,
    registry_id: uuid.UUID,
) -> MedicationRegistry | None:
    """Fetch a single MedicationRegistry row by primary key.

    Args:
        session (AsyncSession): Active async database session.
        registry_id (uuid.UUID): UUID of the registry row.

    Returns:
        MedicationRegistry | None: The MedicationRegistry instance, or None if not found.

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
        session (AsyncSession): Active async database session.
        user_id (uuid.UUID): UUID of the authenticated user.
        registry_id (uuid.UUID): UUID of the medication registry row.
        expiry_date (date): Expiry date of the entry.

    Returns:
        CabinetEntry | None: The CabinetEntry if found, otherwise None.

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


def _apply_usage(entry: CabinetEntry, resolved_usage: ResolvedUsage) -> None:
    """Write all usage/dosage fields from resolved_usage onto entry in place."""
    entry.is_used = resolved_usage.is_used
    entry.dosage_times = resolved_usage.dosage_times
    entry.dosage_period = resolved_usage.dosage_period
    entry.dosage_amount = resolved_usage.dosage_amount
    entry.dosage_start_date = resolved_usage.dosage_start_date
    entry.dosage_end_date = resolved_usage.dosage_end_date


async def insert_entry(
    session: AsyncSession,
    user_id: uuid.UUID,
    registry_id: uuid.UUID,
    package_count: int,
    partial_tablet_count: int | None,
    expiry_date: date,
    is_important: bool = False,
    resolved_usage: ResolvedUsage | None = None,
) -> CabinetEntry:
    """Insert a new cabinet entry and flush to obtain its ID.

    Args:
        session (AsyncSession): Active async database session.
        user_id (uuid.UUID): UUID of the authenticated user.
        registry_id (uuid.UUID): UUID of the medication registry row.
        package_count (int): Number of packages.
        partial_tablet_count (int | None): Tablets in the last (partial) package, or None.
        expiry_date (date): Expiry date for the entry.
        is_important (bool): Whether the entry is marked important.
        resolved_usage (ResolvedUsage | None): Validated usage fields to persist, or None.

    Returns:
        CabinetEntry: The newly created CabinetEntry (committed).

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
        is_important=is_important,
    )
    if resolved_usage is not None:
        _apply_usage(entry, resolved_usage)
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


async def update_entry_usage(
    session: AsyncSession,
    entry: CabinetEntry,
    resolved_usage: ResolvedUsage,
) -> CabinetEntry:
    """Write usage/dosage columns onto an existing cabinet entry and persist it.

    Args:
        session (AsyncSession): Active async database session.
        entry (CabinetEntry): The CabinetEntry to update.
        resolved_usage (ResolvedUsage): Validated usage values; when is_used is False all
            dosage/date columns are set to None.

    Returns:
        CabinetEntry: The updated CabinetEntry (committed).

    Raises:
        CabinetDatabaseError: If the flush or commit fails.
    """
    _apply_usage(entry, resolved_usage)
    try:
        async with persist(session, entry):
            session.add(entry)
    except SQLAlchemyError as exc:
        logger.error(
            "Failed to update usage for cabinet entry %s: %s",
            entry.id,
            exc,
            exc_info=True,
        )
        raise CabinetDatabaseError() from exc
    return entry


def _sufficiency_clauses(today: date, sufficiency: str):
    """Build WHERE clauses filtering used tablet entries by sufficiency verdict.

    Mirrors the canonical Python calc in ``cabinet.service``: ``total_tablets``,
    ``daily_consumption_rate``, ``days_of_supply_from_rate`` and the
    ``is_sufficient`` verdict in ``compute_usage_view``. SQL cannot call that
    per-row Python code, so the arithmetic is duplicated here; the two paths are
    pinned together by the parity tests in ``tests/cabinet/test_crud.py``. Change
    both together if the calc ever changes (Risk #6).

    The guards reproduce ``compute_usage_view``'s None cases so a row matches
    neither filter exactly when the Python calc yields ``is_sufficient is None``:

    * ``dosage_end_date > today`` mirrors the ``until_end > 0`` gate — once the
      window is closed (end date today or past) there is no verdict.
    * Dividing by ``NULLIF(daily_rate, 0)`` mirrors ``days_of_supply_from_rate``
      returning None for ``daily_rate <= 0``: a zero rate yields a NULL supply,
      so the verdict is NULL and the row matches neither filter — and there is no
      divide-by-zero regardless of WHERE evaluation order.

    Args:
        today (date): Reference date for the supply projection.
        sufficiency (str): "insufficient" or "sufficient".

    Returns:
        list: SQLAlchemy boolean clauses to AND into the query's WHERE.
    """
    # total_tablets is not a DB column — compute from package_count,
    # partial_tablet_count, and MedicationRegistry.capacity (tablets per package),
    # matching service.total_tablets():
    #   if partial_tablet_count is not None: (pkg_count - 1) * tpp + partial
    #   else: pkg_count * tpp
    tpp_expr = cast(col(MedicationRegistry.capacity), Integer)
    total_tablets_expr = cast(
        case(
            (
                col(CabinetEntry.partial_tablet_count).is_not(None),
                (col(CabinetEntry.package_count) - 1) * tpp_expr
                + col(CabinetEntry.partial_tablet_count),
            ),
            else_=col(CabinetEntry.package_count) * tpp_expr,
        ),
        Float,
    )
    period_days_expr = case(
        (col(CabinetEntry.dosage_period) == "day", literal(1.0)),
        else_=literal(7.0),
    )
    daily_rate_expr = (
        cast(col(CabinetEntry.dosage_times) * col(CabinetEntry.dosage_amount), Float)
        / period_days_expr
    )
    # NULLIF(rate, 0) -> NULL supply on a zero rate (mirrors the Python None-guard
    # and removes the divide-by-zero F4 flagged), independent of clause order.
    days_supply_expr = cast(
        func.floor(total_tablets_expr / func.nullif(daily_rate_expr, literal(0.0))),
        Integer,
    )
    # Reframe as a date comparison to avoid date-minus-date type ambiguity.
    # PostgreSQL adds integer days to a date natively.
    projected_finish_expr = literal(today) + days_supply_expr
    end_date_col = col(CabinetEntry.dosage_end_date)
    verdict = (
        projected_finish_expr < end_date_col
        if sufficiency == "insufficient"
        else projected_finish_expr >= end_date_col
    )
    return [
        col(CabinetEntry.is_used).is_(True),
        end_date_col.is_not(None),
        # F2: closed window (until_end <= 0) yields no verdict
        end_date_col > literal(today),
        col(MedicationRegistry.capacity).is_not(None),
        col(CabinetEntry.dosage_times).is_not(None),
        col(CabinetEntry.dosage_amount).is_not(None),
        verdict,
    ]


def _build_base_query(
    user_id: uuid.UUID,
    today: date,
    threshold: int,
    status: str | None,
    tsquery: str | None,
    category: str | None = None,
    below_minimum: bool | None = None,
    min_package_count: int | None = None,
    sufficiency: str | None = None,
):
    """Build the filtered join query (no ORDER BY / LIMIT / OFFSET).

    Args:
        user_id (uuid.UUID): UUID of the authenticated user.
        today (date): Reference date for status computation.
        threshold (int): Expiry threshold in days.
        status (str | None): Optional status filter ("valid", "expiring", "expired").
        tsquery (str | None): Optional safe prefix tsquery string for full-text search.
        category (str | None): Optional category filter ("important" filters to important entries).
        below_minimum (bool | None): When True, filter to important entries below the package minimum.
        sufficiency (str | None): "insufficient" or "sufficient" — filters used tablet entries by whether days of supply is less than or at least days until end date.
        min_package_count (int | None): User's minimum package count; required when below_minimum is True.

    Returns:
        Select: A SQLAlchemy select construct with all WHERE clauses applied.
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
    if category == "important":
        stmt = stmt.where(col(CabinetEntry.is_important).is_(True))
    elif category == "used":
        stmt = stmt.where(col(CabinetEntry.is_used).is_(True))
    if below_minimum and min_package_count is not None:
        # Must stay in sync with cabinet.service.is_below_minimum, which encodes the
        # same rule (important AND package_count < minimum) for the per-row badge.
        # The set-based filter cannot call that per-row predicate, so the rule is
        # duplicated here; change both together if the comparison ever changes.
        stmt = stmt.where(
            col(CabinetEntry.is_important).is_(True),
            col(CabinetEntry.package_count) < min_package_count,
        )
    if sufficiency in ("insufficient", "sufficient"):
        stmt = stmt.where(*_sufficiency_clauses(today, sufficiency))
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
    category: str | None = None,
    below_minimum: bool | None = None,
    min_package_count: int | None = None,
    sufficiency: str | None = None,
) -> tuple[list[tuple[CabinetEntry, MedicationRegistry]], int]:
    """Fetch a filtered, sorted, paginated page of cabinet entries plus total count.

    Args:
        session (AsyncSession): Active async database session.
        user_id (uuid.UUID): UUID of the authenticated user.
        today (date): Reference date for status SQL predicates.
        threshold (int): Expiry threshold days for status SQL predicates.
        status (str | None): Optional status filter ("valid", "expiring", "expired").
        tsquery (str | None): Optional safe prefix tsquery string for full-text search.
        order (str): Sort direction for medication name ("asc" or "desc").
        limit (int): Page size.
        offset (int): Row offset for pagination.
        category (str | None): Optional category filter ("important" filters to important entries).
        below_minimum (bool | None): When True, filter to important entries below the package minimum.
        sufficiency (str | None): "insufficient" or "sufficient" — filters used tablet entries by whether days of supply is less than or at least days until end date.
        min_package_count (int | None): User's minimum package count; required when below_minimum is True.

    Returns:
        tuple[list[tuple[CabinetEntry, MedicationRegistry]], int]: Tuple of (page rows, total count under the same filters).

    Raises:
        CabinetDatabaseError: If any database query fails.
    """
    base = _build_base_query(
        user_id,
        today,
        threshold,
        status,
        tsquery,
        category,
        below_minimum,
        min_package_count,
        sufficiency,
    )

    name_col = func.lower(col(MedicationRegistry.name))
    order_clause = name_col.asc() if order == "asc" else name_col.desc()

    page_q = (
        base.order_by(order_clause, col(CabinetEntry.id).asc())
        .limit(limit)
        .offset(offset)
    )

    count_q = select(func.count()).select_from(
        _build_base_query(
            user_id,
            today,
            threshold,
            status,
            tsquery,
            category,
            below_minimum,
            min_package_count,
            sufficiency,
        ).subquery()
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


async def find_entry_by_id(
    session: AsyncSession,
    user_id: uuid.UUID,
    entry_id: uuid.UUID,
) -> CabinetEntry | None:
    """Look up a cabinet entry by its primary key, scoped to the user.

    Args:
        session (AsyncSession): Active async database session.
        user_id (uuid.UUID): UUID of the authenticated user.
        entry_id (uuid.UUID): UUID of the cabinet entry.

    Returns:
        CabinetEntry | None: The CabinetEntry if found and owned by the user, otherwise None.

    Raises:
        CabinetDatabaseError: If the database query fails.
    """
    try:
        result = await session.execute(
            select(CabinetEntry).where(
                col(CabinetEntry.id) == entry_id,
                col(CabinetEntry.user_id) == user_id,
            )
        )
    except SQLAlchemyError as exc:
        logger.error(
            "Failed to fetch cabinet entry %s for user %s: %s",
            entry_id,
            user_id,
            exc,
            exc_info=True,
        )
        raise CabinetDatabaseError() from exc
    return result.scalar_one_or_none()


async def update_entry_importance(
    session: AsyncSession,
    entry: CabinetEntry,
    is_important: bool,
) -> CabinetEntry:
    """Set the importance flag on a cabinet entry and persist it.

    Args:
        session (AsyncSession): Active async database session.
        entry (CabinetEntry): The CabinetEntry to update.
        is_important (bool): New importance flag value.

    Returns:
        CabinetEntry: The updated CabinetEntry (committed).

    Raises:
        CabinetDatabaseError: If the flush or commit fails.
    """
    entry.is_important = is_important
    try:
        async with persist(session, entry):
            session.add(entry)
    except SQLAlchemyError as exc:
        logger.error(
            "Failed to update importance for cabinet entry %s: %s",
            entry.id,
            exc,
            exc_info=True,
        )
        raise CabinetDatabaseError() from exc
    return entry


async def update_entry_counts(
    session: AsyncSession,
    entry: CabinetEntry,
    package_count: int,
    partial_tablet_count: int | None,
    is_important: bool | None = None,
    resolved_usage: ResolvedUsage | None = None,
) -> CabinetEntry:
    """Update the package and partial-tablet counts of an existing entry.

    Args:
        session (AsyncSession): Active async database session.
        entry (CabinetEntry): The CabinetEntry to update.
        package_count (int): New package count.
        partial_tablet_count (int | None): New partial tablet count, or None.
        is_important (bool | None): When provided, also update the importance flag.
        resolved_usage (ResolvedUsage | None): When provided, also write the usage/dosage
            columns in the same transaction so counts and usage commit atomically (used by
            the dedup merge path).

    Returns:
        CabinetEntry: The updated CabinetEntry (committed).

    Raises:
        CabinetDatabaseError: If the flush or commit fails.
    """
    entry.package_count = package_count
    entry.partial_tablet_count = partial_tablet_count
    if is_important is not None:
        entry.is_important = is_important
    if resolved_usage is not None:
        _apply_usage(entry, resolved_usage)
    try:
        async with persist(session, entry):
            session.add(entry)
    except SQLAlchemyError as exc:
        logger.error(
            "Failed to update cabinet entry %s: %s", entry.id, exc, exc_info=True
        )
        raise CabinetDatabaseError() from exc
    return entry


async def delete_entry(session: AsyncSession, entry: CabinetEntry) -> None:
    """Delete a cabinet entry and commit.

    Args:
        session (AsyncSession): Active async database session.
        entry (CabinetEntry): The CabinetEntry to delete.

    Raises:
        CabinetDatabaseError: If the delete or commit fails.
    """
    try:
        await session.delete(entry)
        await session.commit()
    except SQLAlchemyError as exc:
        logger.error(
            "Failed to delete cabinet entry %s: %s", entry.id, exc, exc_info=True
        )
        raise CabinetDatabaseError() from exc


async def delete_by_user(session: AsyncSession, user_id: uuid.UUID) -> None:
    """Delete all cabinet entries owned by a user, on the shared session.

    Executes the delete statement only — no commit, no persist. Callers own
    the transaction (see the users-domain facade's account-deletion flow).

    Args:
        session (AsyncSession): Active async database session.
        user_id (uuid.UUID): UUID of the user whose entries are being removed.

    Raises:
        CabinetDatabaseError: If the delete statement fails.
    """
    try:
        await session.execute(
            delete(CabinetEntry).where(col(CabinetEntry.user_id) == user_id)
        )
    except SQLAlchemyError as exc:
        logger.error(
            "Failed to delete cabinet entries for user %s: %s",
            user_id,
            exc,
            exc_info=True,
        )
        raise CabinetDatabaseError() from exc
