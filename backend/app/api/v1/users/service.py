"""Users service: business logic and orchestration."""

import logging
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.users import crud
from app.api.v1.users.models import UserPreferences
from app.api.v1.users.schemas import UserPreferencesOut
from app.utilities.const import (
    DEFAULT_CLOSE_TO_FINISH_THRESHOLD_DAYS,
    DEFAULT_EXPIRY_THRESHOLD_DAYS,
    DEFAULT_MIN_PACKAGE_COUNT,
)

logger = logging.getLogger("app.users.service")


async def get_user_preferences(
    session: AsyncSession,
    user_id: uuid.UUID,
) -> UserPreferences | None:
    """Return the preferences for a user, or None if not yet provisioned.

    Args:
        session (AsyncSession): Active async database session.
        user_id (uuid.UUID): UUID of the user.

    Returns:
        UserPreferences | None: The UserPreferences instance, or None if not found.
    """
    return await crud.get_user_preferences(session, user_id)


async def update_preferences(
    session: AsyncSession,
    user_id: uuid.UUID,
    min_package_count: int,
) -> UserPreferencesOut:
    """Upsert min_package_count and return the effective preferences.

    Args:
        session (AsyncSession): Active async database session.
        user_id (uuid.UUID): UUID of the user.
        min_package_count (int): New minimum package count (1-10).

    Returns:
        UserPreferencesOut: with the updated values.

    Raises:
        UserDatabaseError: If the database operation fails.
    """
    existing = await crud.get_user_preferences(session=session, user_id=user_id)
    if existing is not None:
        prefs = await crud.update_min_package_count(
            session=session,
            prefs=existing,
            min_package_count=min_package_count,
        )
    else:
        new_prefs = UserPreferences(
            user_id=user_id,
            expiry_threshold_days=DEFAULT_EXPIRY_THRESHOLD_DAYS,
            close_to_finish_threshold_days=DEFAULT_CLOSE_TO_FINISH_THRESHOLD_DAYS,
            min_package_count=min_package_count,
        )
        prefs = await crud.insert_preferences(session=session, prefs=new_prefs)
    logger.info(
        "Updated preferences for user %s: min_package_count=%d",
        user_id,
        prefs.min_package_count,
    )
    return UserPreferencesOut(
        expiry_threshold_days=prefs.expiry_threshold_days,
        close_to_finish_threshold_days=prefs.close_to_finish_threshold_days,
        min_package_count=prefs.min_package_count,
    )


async def delete_user_rows(session: AsyncSession, user_id: uuid.UUID) -> None:
    """Delete a user's preferences row and users row, on the shared session.

    Args:
        session (AsyncSession): Active async database session.
        user_id (uuid.UUID): UUID of the user being deleted.

    Raises:
        UserDatabaseError: If either delete statement fails.
    """
    await crud.delete_user_rows(session=session, user_id=user_id)


async def get_effective_preferences(
    session: AsyncSession,
    user_id: uuid.UUID,
) -> UserPreferencesOut:
    """Return the user's effective preferences, falling back to defaults when no row exists.

    Args:
        session (AsyncSession): Active async database session.
        user_id (uuid.UUID): UUID of the user.

    Returns:
        UserPreferencesOut: with stored or default values.

    Raises:
        UserDatabaseError: If the underlying preferences read fails.
    """
    prefs = await crud.get_user_preferences(session, user_id)
    if prefs is None:
        return UserPreferencesOut(
            expiry_threshold_days=DEFAULT_EXPIRY_THRESHOLD_DAYS,
            close_to_finish_threshold_days=DEFAULT_CLOSE_TO_FINISH_THRESHOLD_DAYS,
            min_package_count=DEFAULT_MIN_PACKAGE_COUNT,
        )
    return UserPreferencesOut(
        expiry_threshold_days=prefs.expiry_threshold_days,
        close_to_finish_threshold_days=prefs.close_to_finish_threshold_days,
        min_package_count=prefs.min_package_count,
    )
