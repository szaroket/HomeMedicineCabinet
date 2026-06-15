"""Users database operations."""

import logging
import uuid

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import col

from app.api.v1.users.models import UserPreferences
from app.utilities.errors import UserDatabaseError

logger = logging.getLogger("app.users.crud")


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
