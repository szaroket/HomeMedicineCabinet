"""Cabinet facade: cross-domain orchestration between router and service.

This is the only layer permitted to call services or cruds from other domains.
Routers call the facade; the facade calls this domain's service plus any foreign
domain as needed, then returns the result.
"""

import uuid
from typing import NamedTuple

from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.cabinet import service as cabinet_service
from app.api.v1.cabinet.schemas import CabinetEntryOut, CabinetPageOut, UsageFields
from app.api.v1.users import service as users_service
from app.utilities.const import DEFAULT_EXPIRY_THRESHOLD_DAYS, DEFAULT_MIN_PACKAGE_COUNT


class _ResolvedPrefs(NamedTuple):
    expiry_threshold_days: int
    min_package_count: int


async def _resolve_prefs(session: AsyncSession, user_id: uuid.UUID) -> _ResolvedPrefs:
    """Fetch user preferences and fall back to defaults when no row exists.

    Args:
        session (AsyncSession): Active async database session.
        user_id (uuid.UUID): Authenticated user's UUID.

    Returns:
        _ResolvedPrefs: with expiry_threshold_days and min_package_count.
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
    sufficiency: str | None = None,
) -> CabinetPageOut:
    """Return the current user's cabinet entries with computed status, filtered and paginated.

    Fetches user preferences from the users domain, then delegates to the cabinet service.

    Args:
        session (AsyncSession): Active async database session.
        user_id (uuid.UUID): Authenticated user's UUID.
        status (str | None): Optional status filter ("valid", "expiring", "expired").
        search (str | None): Optional raw search string (name or active ingredient).
        order (str): Sort direction for medication name ("asc" or "desc").
        page (int): 1-based page number.
        page_size (int): Number of items per page.
        category (str | None): Optional category filter ("important" filters to important entries).
        below_minimum (bool | None): When True, filter to important entries below the package minimum.
        sufficiency (str | None): "insufficient" or "sufficient" — filters used tablet entries by sufficiency verdict.

    Returns:
        CabinetPageOut: with items, total, page, and page_size.
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
        sufficiency=sufficiency,
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
        session (AsyncSession): Active async database session.
        user_id (uuid.UUID): Authenticated user's UUID.
        entry_id (uuid.UUID): UUID of the cabinet entry to update.
        is_important (bool): New importance flag value.

    Returns:
        CabinetEntryOut: The updated CabinetEntryOut.
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


async def set_entry_usage(
    session: AsyncSession,
    user_id: uuid.UUID,
    entry_id: uuid.UUID,
    usage: UsageFields,
) -> CabinetEntryOut:
    """Set, update, or clear the usage/dosage schedule on a cabinet entry.

    Fetches user preferences to resolve thresholds, then delegates to the cabinet service.

    Args:
        session (AsyncSession): Active async database session.
        user_id (uuid.UUID): Authenticated user's UUID.
        entry_id (uuid.UUID): UUID of the cabinet entry to update.
        usage (UsageFields): Incoming usage payload.

    Returns:
        CabinetEntryOut: The updated entry with recomputed usage view.
    """
    resolved = await _resolve_prefs(session, user_id)
    return await cabinet_service.set_entry_usage(
        session=session,
        user_id=user_id,
        entry_id=entry_id,
        usage=usage,
        expiry_threshold_days=resolved.expiry_threshold_days,
        min_package_count=resolved.min_package_count,
    )


async def set_entry_quantity(
    session: AsyncSession,
    user_id: uuid.UUID,
    entry_id: uuid.UUID,
    package_count: int,
    partial_tablet_count: int | None,
) -> CabinetEntryOut:
    """Set the absolute package and partial-tablet counts on a cabinet entry.

    Fetches user preferences to resolve thresholds, then delegates to the cabinet service.

    Args:
        session (AsyncSession): Active async database session.
        user_id (uuid.UUID): Authenticated user's UUID.
        entry_id (uuid.UUID): UUID of the cabinet entry to update.
        package_count (int): New absolute package count (>= 0).
        partial_tablet_count (int | None): New partial tablet count, or None for a full package.

    Returns:
        CabinetEntryOut: The updated entry with recomputed status and below_minimum.
    """
    resolved = await _resolve_prefs(session, user_id)
    return await cabinet_service.set_entry_quantity(
        session=session,
        user_id=user_id,
        entry_id=entry_id,
        package_count=package_count,
        partial_tablet_count=partial_tablet_count,
        expiry_threshold_days=resolved.expiry_threshold_days,
        min_package_count=resolved.min_package_count,
    )
