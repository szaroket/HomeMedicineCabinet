"""Notifications database operations."""

import logging
import uuid

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import col

from app.api.v1.notifications.models import DismissedNotification
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
