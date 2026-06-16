"""Cabinet facade: cross-domain orchestration between router and service.

This is the only layer permitted to call services or cruds from other domains.
Routers call the facade; the facade calls this domain's service plus any foreign
domain as needed, then returns the result.
"""

import uuid
from typing import NamedTuple

from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.cabinet import service as cabinet_service
from app.api.v1.cabinet.schemas import CabinetEntryOut, CabinetPageOut
from app.api.v1.users import service as users_service
from app.utilities.const import DEFAULT_EXPIRY_THRESHOLD_DAYS, DEFAULT_MIN_PACKAGE_COUNT


class _ResolvedPrefs(NamedTuple):
    expiry_threshold_days: int
    min_package_count: int


async def _resolve_prefs(session: AsyncSession, user_id: uuid.UUID) -> _ResolvedPrefs:
    """Fetch user preferences and fall back to defaults when no row exists.

    Args:
        session: Active async database session.
        user_id: Authenticated user's UUID.

    Returns:
        _ResolvedPrefs with expiry_threshold_days and min_package_count.
    """
    prefs = await users_service.get_user_preferences(session, user_id)
    return _ResolvedPrefs(
        expiry_threshold_days=(
            prefs.expiry_threshold_days
            if prefs is not None
            else DEFAULT_EXPIRY_THRESHOLD_DAYS
        ),
        min_package_count=(
            prefs.min_package_count if prefs is not None else DEFAULT_MIN_PACKAGE_COUNT
        ),
    )


async def list_entries(
    session: AsyncSession,
    user_id: uuid.UUID,
    status: str | None = None,
    search: str | None = None,
    order: str = "asc",
    page: int = 1,
    page_size: int = 20,
    category: str | None = None,
    below_minimum: bool | None = None,
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
        below_minimum: When True, filter to important entries below the package minimum.

    Returns:
        CabinetPageOut with items, total, page, and page_size.
    """
    resolved = await _resolve_prefs(session, user_id)
    return await cabinet_service.list_entries(
        session=session,
        user_id=user_id,
        expiry_threshold_days=resolved.expiry_threshold_days,
        status=status,
        search=search,
        order=order,
        page=page,
        page_size=page_size,
        min_package_count=resolved.min_package_count,
        category=category,
        below_minimum=below_minimum,
    )


async def set_entry_importance(
    session: AsyncSession,
    user_id: uuid.UUID,
    entry_id: uuid.UUID,
    is_important: bool,
) -> CabinetEntryOut:
    """Toggle the importance flag on a cabinet entry owned by the user.

    Fetches user preferences to resolve thresholds, then delegates to the cabinet service.

    Args:
        session: Active async database session.
        user_id: Authenticated user's UUID.
        entry_id: UUID of the cabinet entry to update.
        is_important: New importance flag value.

    Returns:
        The updated CabinetEntryOut.
    """
    resolved = await _resolve_prefs(session, user_id)
    return await cabinet_service.set_entry_importance(
        session=session,
        user_id=user_id,
        entry_id=entry_id,
        is_important=is_important,
        expiry_threshold_days=resolved.expiry_threshold_days,
        min_package_count=resolved.min_package_count,
    )
