"""Cabinet facade: cross-domain orchestration between router and service.

This is the only layer permitted to call services or cruds from other domains.
Routers call the facade; the facade calls this domain's service plus any foreign
domain as needed, then returns the result.
"""

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.cabinet import service as cabinet_service
from app.api.v1.cabinet.schemas import CabinetEntryOut
from app.api.v1.users import service as users_service
from app.utilities.const import DEFAULT_EXPIRY_THRESHOLD_DAYS


async def list_entries(
    session: AsyncSession,
    user_id: uuid.UUID,
) -> list[CabinetEntryOut]:
    """Return the current user's cabinet entries with computed status.

    Fetches user preferences from the users domain, then delegates to the
    cabinet service for the domain logic.

    Args:
        session: Active async database session.
        user_id: Authenticated user's UUID.

    Returns:
        List of CabinetEntryOut items ordered by medication name.
    """
    prefs = await users_service.get_user_preferences(session, user_id)
    threshold = (
        prefs.expiry_threshold_days
        if prefs is not None
        else DEFAULT_EXPIRY_THRESHOLD_DAYS
    )
    return await cabinet_service.list_entries(
        session=session,
        user_id=user_id,
        expiry_threshold_days=threshold,
    )
