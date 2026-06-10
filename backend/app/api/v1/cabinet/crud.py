"""Cabinet database operations."""

import logging
import uuid
from datetime import date

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlmodel import col
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.cabinet.models import CabinetEntry
from app.api.v1.medicines.models import MedicationRegistry
from app.api.v1.users.models import UserPreferences
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


async def get_user_preferences(
    session: AsyncSession,
    user_id: uuid.UUID,
) -> UserPreferences | None:
    """Fetch the UserPreferences row for a given user.

    Args:
        session: Active async database session.
        user_id: UUID of the user.

    Returns:
        The UserPreferences instance, or None if not found.

    Raises:
        CabinetDatabaseError: If the database query fails.
    """
    try:
        result = await session.execute(
            select(UserPreferences).where(col(UserPreferences.user_id) == user_id)
        )
    except SQLAlchemyError as exc:
        logger.error(
            "Failed to fetch preferences for user %s: %s", user_id, exc, exc_info=True
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
        CabinetDatabaseError: If the insert, flush, or commit fails.
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
    except SQLAlchemyError as exc:
        logger.error("Failed to insert cabinet entry: %s", exc, exc_info=True)
        raise CabinetDatabaseError() from exc
    return entry


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
