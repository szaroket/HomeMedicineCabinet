"""Cabinet facade: cross-domain orchestration between router and service.

This is the only layer permitted to call services or cruds from other domains.
Routers call the facade; the facade calls this domain's service plus any foreign
domain as needed, then returns the result.
"""

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.cabinet import service as cabinet_service
from app.api.v1.cabinet.schemas import CabinetPageOut
from app.api.v1.users import service as users_service
from app.utilities.const import DEFAULT_EXPIRY_THRESHOLD_DAYS, DEFAULT_MIN_PACKAGE_COUNT


async def list_entries(
    session: AsyncSession,
    user_id: uuid.UUID,
    status: str | None = None,
    search: str | None = None,
    order: str = "asc",
    page: int = 1,
    page_size: int = 20,
    category: str | None = None,
) -> CabinetPageOut:
    """Return the current user's cabinet entries with computed status, filtered and paginated.

    Fetches user preferences from the users domain, then delegates to the cabinet service.

    Args:
        session: Active async database session.
        user_id: Authenticated user's UUID.
        status: Optional status filter ("valid", "expiring", "expired").
        search: Optional raw search string (name or active ingredient).
        order: Sort direction for medication name ("asc" or "desc").
        page: 1-based page number.
        page_size: Number of items per page.
        category: Optional category filter ("important" filters to important entries).

    Returns:
        CabinetPageOut with items, total, page, and page_size.
    """
    prefs = await users_service.get_user_preferences(session, user_id)
    threshold = (
        prefs.expiry_threshold_days
        if prefs is not None
        else DEFAULT_EXPIRY_THRESHOLD_DAYS
    )
    min_package_count = (
        prefs.min_package_count if prefs is not None else DEFAULT_MIN_PACKAGE_COUNT
    )
    return await cabinet_service.list_entries(
        session=session,
        user_id=user_id,
        expiry_threshold_days=threshold,
        status=status,
        search=search,
        order=order,
        page=page,
        page_size=page_size,
        min_package_count=min_package_count,
        category=category,
    )
