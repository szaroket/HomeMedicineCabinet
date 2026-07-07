"""Notifications database operations."""

import logging
import uuid

from sqlalchemy import delete, select, tuple_
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import col

from app.api.v1.notifications.models import DismissedNotification
from app.db.connector import persist
from app.utilities.errors import NotificationsDatabaseError

logger = logging.getLogger("app.notifications.crud")


async def get_dismissals(
    session: AsyncSession,
    user_id: uuid.UUID,
) -> list[DismissedNotification]:
    """Fetch all dismissal rows for a user.

    Args:
        session (AsyncSession): Active async database session.
        user_id (uuid.UUID): UUID of the authenticated user.

    Returns:
        list[DismissedNotification]: The user's dismissal rows.

    Raises:
        NotificationsDatabaseError: If the database query fails.
    """
    try:
        result = await session.execute(
            select(DismissedNotification).where(
                col(DismissedNotification.user_id) == user_id
            )
        )
    except SQLAlchemyError as exc:
        logger.error(
            "Failed to fetch dismissals for user %s: %s", user_id, exc, exc_info=True
        )
        raise NotificationsDatabaseError() from exc
    return list(result.scalars().all())


async def insert_dismissal(
    session: AsyncSession,
    user_id: uuid.UUID,
    cabinet_entry_id: uuid.UUID,
    trigger_type: str,
) -> None:
    """Insert a dismissal row, treating a concurrent duplicate as success.

    Args:
        session (AsyncSession): Active async database session.
        user_id (uuid.UUID): UUID of the authenticated user.
        cabinet_entry_id (uuid.UUID): UUID of the dismissed entry.
        trigger_type (str): The trigger type being dismissed.

    Raises:
        NotificationsDatabaseError: If the insert fails for a reason other than
            the unique-constraint race.
    """
    row = DismissedNotification(
        user_id=user_id,
        cabinet_entry_id=cabinet_entry_id,
        trigger_type=trigger_type,
    )
    try:
        async with persist(session, row):
            session.add(row)
    except IntegrityError:
        # persist() already rolled back; a concurrent duplicate dismissal means
        # the row already exists, so the caller's intent is already satisfied.
        pass
    except SQLAlchemyError as exc:
        logger.error(
            "Failed to insert dismissal for user %s, entry %s, trigger %s: %s",
            user_id,
            cabinet_entry_id,
            trigger_type,
            exc,
            exc_info=True,
        )
        raise NotificationsDatabaseError() from exc


async def delete_stale_dismissals(
    session: AsyncSession,
    user_id: uuid.UUID,
    stale_keys: set[tuple[uuid.UUID, str]],
) -> None:
    """Delete the user's dismissal rows matching the given (entry, trigger) keys.

    Args:
        session (AsyncSession): Active async database session.
        user_id (uuid.UUID): UUID of the authenticated user.
        stale_keys (set[tuple[uuid.UUID, str]]): The (cabinet_entry_id,
            trigger_type) pairs whose condition has cleared and should be
            garbage-collected. Must be non-empty; the caller skips the call
            entirely when there is nothing stale.

    Raises:
        NotificationsDatabaseError: If the delete fails.
    """
    try:
        async with persist(session):
            await session.execute(
                delete(DismissedNotification).where(
                    col(DismissedNotification.user_id) == user_id,
                    tuple_(
                        DismissedNotification.cabinet_entry_id,
                        DismissedNotification.trigger_type,
                    ).in_(stale_keys),
                )
            )
    except SQLAlchemyError as exc:
        logger.error(
            "Failed to delete stale dismissals for user %s: %s",
            user_id,
            exc,
            exc_info=True,
        )
        raise NotificationsDatabaseError() from exc
