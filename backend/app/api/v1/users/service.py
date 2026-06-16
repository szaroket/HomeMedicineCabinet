"""Users service: business logic and orchestration."""

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


async def get_user_preferences(
    session: AsyncSession,
    user_id: uuid.UUID,
) -> UserPreferences | None:
    """Return the preferences for a user, or None if not yet provisioned.

    Args:
        session: Active async database session.
        user_id: UUID of the user.

    Returns:
        The UserPreferences instance, or None if not found.
    """
    return await crud.get_user_preferences(session, user_id)


async def get_effective_preferences(
    session: AsyncSession,
    user_id: uuid.UUID,
) -> UserPreferencesOut:
    """Return the user's effective preferences, falling back to defaults when no row exists.

    Args:
        session: Active async database session.
        user_id: UUID of the user.

    Returns:
        UserPreferencesOut with stored or default values.

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
