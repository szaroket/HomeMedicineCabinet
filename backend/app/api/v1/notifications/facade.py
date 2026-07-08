"""Notifications facade: cross-domain orchestration for the notification center."""

import logging
import uuid
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.cabinet import service as cabinet_service
from app.api.v1.notifications import service as notifications_service
from app.api.v1.notifications.schemas import DismissRequest, NotificationListOut
from app.api.v1.users import service as users_service

logger = logging.getLogger("app.notifications.facade")


async def list_notifications(
    session: AsyncSession,
    user_id: uuid.UUID,
) -> NotificationListOut:
    """Compute the user's active, non-dismissed notifications in urgency order.

    Fetches effective preferences and the user's computed cabinet entries
    cross-domain, reads the user's dismissals, then delegates trigger
    evaluation, dismissal filtering, and ordering to the notifications service.

    Args:
        session (AsyncSession): Active async database session.
        user_id (uuid.UUID): Authenticated user's UUID.

    Returns:
        NotificationListOut: The active, non-dismissed notifications, ordered.

    Raises:
        UserDatabaseError: If reading preferences fails.
        CabinetDatabaseError: If reading cabinet entries fails.
        NotificationsDatabaseError: If reading dismissals fails.
    """
    prefs = await users_service.get_effective_preferences(
        session=session, user_id=user_id
    )
    entries = await cabinet_service.list_all_for_user(
        session=session,
        user_id=user_id,
        expiry_threshold_days=prefs.expiry_threshold_days,
        min_package_count=prefs.min_package_count,
    )
    dismissals = await notifications_service.get_dismissals(
        session=session, user_id=user_id
    )
    today = datetime.now(timezone.utc).date()

    active_items = notifications_service.compute_active_notifications(
        entries=entries,
        close_to_finish_threshold_days=prefs.close_to_finish_threshold_days,
        today=today,
    )
    active_keys = {(item.cabinet_entry_id, item.trigger_type) for item in active_items}
    stale_keys = notifications_service.compute_stale_dismissal_keys(
        dismissals=dismissals, active_keys=active_keys
    )
    if stale_keys:
        await notifications_service.delete_stale_dismissals(
            session=session, user_id=user_id, stale_keys=stale_keys
        )

    dismissed_keys = {(d.cabinet_entry_id, d.trigger_type) for d in dismissals}
    filtered = [
        item
        for item in active_items
        if (item.cabinet_entry_id, item.trigger_type) not in dismissed_keys
    ]
    return NotificationListOut(
        items=notifications_service.order_notifications(filtered)
    )


async def dismiss(
    session: AsyncSession,
    user_id: uuid.UUID,
    request: DismissRequest,
) -> None:
    """Record a dismissal for the given entry/trigger.

    Args:
        session (AsyncSession): Active async database session.
        user_id (uuid.UUID): Authenticated user's UUID.
        request (DismissRequest): The entry and trigger type being dismissed.

    Raises:
        DismissalEntryNotFoundError: If the referenced cabinet entry does not exist.
        NotificationsDatabaseError: If the insert fails.
    """
    await notifications_service.insert_dismissal(
        session=session, user_id=user_id, request=request
    )
