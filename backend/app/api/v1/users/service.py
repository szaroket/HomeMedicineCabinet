"""Users service: business logic and orchestration."""

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.users import crud
from app.api.v1.users.models import UserPreferences


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
