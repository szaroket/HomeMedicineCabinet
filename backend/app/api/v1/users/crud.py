"""Users database operations."""

import logging
import uuid
from datetime import datetime, timezone

from sqlalchemy import delete, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import col

from app.api.v1.users.models import User, UserPreferences
from app.db.connector import persist
from app.utilities.errors import UserDatabaseError

logger = logging.getLogger("app.users.crud")


async def get_user_preferences(
    session: AsyncSession,
    user_id: uuid.UUID,
) -> UserPreferences | None:
    """Fetch the UserPreferences row for a given user.

    Args:
        session (AsyncSession): Active async database session.
        user_id (uuid.UUID): UUID of the user.

    Returns:
        UserPreferences | None: The UserPreferences instance, or None if not found.

    Raises:
        UserDatabaseError: If the database query fails.
    """
    try:
        result = await session.execute(
            select(UserPreferences).where(col(UserPreferences.user_id) == user_id)
        )
    except SQLAlchemyError as exc:
        logger.error(
            "Failed to fetch preferences for user %s: %s", user_id, exc, exc_info=True
        )
        raise UserDatabaseError() from exc
    return result.scalar_one_or_none()


async def update_min_package_count(
    session: AsyncSession,
    prefs: UserPreferences,
    min_package_count: int,
) -> UserPreferences:
    """Update min_package_count on an existing preferences row.

    Args:
        session (AsyncSession): Active async database session.
        prefs (UserPreferences): Existing UserPreferences instance to update.
        min_package_count (int): New minimum package count to persist.

    Returns:
        UserPreferences: The updated UserPreferences instance.

    Raises:
        UserDatabaseError: If the flush or commit fails.
    """
    prefs.min_package_count = min_package_count
    prefs.updated_at = datetime.now(timezone.utc)
    try:
        async with persist(session, prefs):
            session.add(prefs)
    except SQLAlchemyError as exc:
        logger.error(
            "Failed to update preferences for user %s: %s",
            prefs.user_id,
            exc,
            exc_info=True,
        )
        raise UserDatabaseError() from exc
    return prefs


async def insert_preferences(
    session: AsyncSession,
    prefs: UserPreferences,
) -> UserPreferences:
    """Persist a new UserPreferences row.

    Args:
        session (AsyncSession): Active async database session.
        prefs (UserPreferences): New UserPreferences instance to insert.

    Returns:
        UserPreferences: The inserted UserPreferences instance.

    Raises:
        UserDatabaseError: If the flush or commit fails.
    """
    try:
        async with persist(session, prefs):
            session.add(prefs)
    except SQLAlchemyError as exc:
        logger.error(
            "Failed to insert preferences for user %s: %s",
            prefs.user_id,
            exc,
            exc_info=True,
        )
        raise UserDatabaseError() from exc
    return prefs


async def delete_user_rows(session: AsyncSession, user_id: uuid.UUID) -> None:
    """Delete a user's preferences row and users row, on the shared session.

    Deletes children before the parent (no DB cascade exists). Executes the
    delete statements only — no commit, no persist. Callers own the
    transaction (see the users-domain facade's account-deletion flow).

    Args:
        session (AsyncSession): Active async database session.
        user_id (uuid.UUID): UUID of the user being deleted.

    Raises:
        UserDatabaseError: If either delete statement fails.
    """
    try:
        await session.execute(
            delete(UserPreferences).where(col(UserPreferences.user_id) == user_id)
        )
        await session.execute(delete(User).where(col(User.id) == user_id))
    except SQLAlchemyError as exc:
        logger.error(
            "Failed to delete local rows for user %s: %s", user_id, exc, exc_info=True
        )
        raise UserDatabaseError() from exc
