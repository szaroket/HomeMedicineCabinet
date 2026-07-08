"""Notifications service: trigger predicates, urgency ordering, assembly, and DB-backed reads.

Reuses the cabinet domain's pure classification/finish-date math (Status,
is_below_minimum, compute_usage_view) via the already-computed CabinetEntryOut
fields; it does not re-derive expiry or finish-date math.
"""

import uuid
from datetime import date
from typing import NamedTuple

from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.cabinet.schemas import CabinetEntryOut
from app.api.v1.cabinet.service import Status
from app.api.v1.notifications import crud
from app.api.v1.notifications.models import DismissedNotification
from app.api.v1.notifications.schemas import (
    DismissRequest,
    NotificationOut,
    TriggerType,
)

_TRIGGER_TYPE_RANK: dict[TriggerType, int] = {
    TriggerType.EXPIRY: 0,
    TriggerType.BELOW_MINIMUM: 1,
    TriggerType.RUN_OUT: 2,
}


def is_expiry_active(entry: CabinetEntryOut) -> bool:
    """Return True when the entry's expiry status warrants an expiry alert.

    Args:
        entry (CabinetEntryOut): A computed cabinet entry row.

    Returns:
        bool: True when status is EXPIRING or EXPIRED.
    """
    return entry.status in (Status.EXPIRING, Status.EXPIRED)


def is_below_minimum_active(entry: CabinetEntryOut) -> bool:
    """Return True when the entry is below the user's minimum package count.

    Args:
        entry (CabinetEntryOut): A computed cabinet entry row.

    Returns:
        bool: The entry's already-computed below_minimum flag.
    """
    return entry.below_minimum


def is_run_out_active(
    entry: CabinetEntryOut, close_to_finish_threshold_days: int
) -> bool:
    """Return True when a used, tablet-based entry risks running out before its end date.

    Args:
        entry (CabinetEntryOut): A computed cabinet entry row.
        close_to_finish_threshold_days (int): Days-of-supply threshold that triggers the alert.

    Returns:
        bool: True when the entry is used + tablet-based with an end date, the
            projected finish is insufficient (is_sufficient is False), and days_of_supply
            is at or under the threshold.
    """
    return (
        entry.is_used
        and entry.is_tablet_based
        and entry.dosage_end_date is not None
        and entry.is_sufficient is False
        and entry.days_of_supply is not None
        and entry.days_of_supply <= close_to_finish_threshold_days
    )


class _UrgencySortKey(NamedTuple):
    """Deterministic urgency sort key — see order_notifications for the ordering rationale."""

    expired_bucket: int
    effective_days: int
    trigger_type_rank: int
    cabinet_entry_id: str


def _sort_key(item: NotificationOut) -> _UrgencySortKey:
    """Build the deterministic urgency sort key for a notification.

    Args:
        item (NotificationOut): The notification to key.

    Returns:
        _UrgencySortKey: The key fields, in tie-break order.
    """
    days_remaining = item.days_remaining
    expired_bucket = 0 if days_remaining is not None and days_remaining < 0 else 1
    effective_days = days_remaining if days_remaining is not None else 0
    return _UrgencySortKey(
        expired_bucket=expired_bucket,
        effective_days=effective_days,
        trigger_type_rank=_TRIGGER_TYPE_RANK[item.trigger_type],
        cabinet_entry_id=str(item.cabinet_entry_id),
    )


async def get_dismissals(
    session: AsyncSession,
    user_id: uuid.UUID,
) -> list[DismissedNotification]:
    """Return all dismissal rows for a user.

    Args:
        session (AsyncSession): Active async database session.
        user_id (uuid.UUID): Authenticated user's UUID.

    Returns:
        list[DismissedNotification]: The user's dismissal rows.

    Raises:
        NotificationsDatabaseError: If the database query fails.
    """
    return await crud.get_dismissals(session=session, user_id=user_id)


def order_notifications(items: list[NotificationOut]) -> list[NotificationOut]:
    """Order notifications most-urgent-first.

    Already-expired items (days_remaining < 0) sort ahead of everything. Among the
    rest, a below_minimum alert (days_remaining is None) sorts as if it had 0 days
    remaining, ahead of any positive-days expiry/run_out item. Same-day ties break
    by a fixed trigger_type order (expiry, below_minimum, run_out), then by
    cabinet_entry_id for full reproducibility.

    Args:
        items (list[NotificationOut]): Unordered active notifications.

    Returns:
        list[NotificationOut]: The same items, sorted most-urgent-first.
    """
    return sorted(items, key=_sort_key)


def compute_active_notifications(
    entries: list[CabinetEntryOut],
    close_to_finish_threshold_days: int,
    today: date,
) -> list[NotificationOut]:
    """Apply the trigger predicates to every entry, unfiltered by dismissal.

    Args:
        entries (list[CabinetEntryOut]): The user's computed cabinet entries.
        close_to_finish_threshold_days (int): Threshold for the run-out trigger.
        today (date): Reference date for computing days-to-expiry.

    Returns:
        list[NotificationOut]: Every currently-active alert, unordered and
            regardless of dismissal state.
    """
    items: list[NotificationOut] = []
    for entry in entries:
        if is_expiry_active(entry):
            items.append(
                NotificationOut(
                    trigger_type=TriggerType.EXPIRY,
                    cabinet_entry_id=entry.id,
                    medication_name=entry.name,
                    days_remaining=(entry.expiry_date - today).days,
                )
            )
        if is_below_minimum_active(entry):
            items.append(
                NotificationOut(
                    trigger_type=TriggerType.BELOW_MINIMUM,
                    cabinet_entry_id=entry.id,
                    medication_name=entry.name,
                    days_remaining=None,
                )
            )
        if is_run_out_active(
            entry, close_to_finish_threshold_days=close_to_finish_threshold_days
        ):
            items.append(
                NotificationOut(
                    trigger_type=TriggerType.RUN_OUT,
                    cabinet_entry_id=entry.id,
                    medication_name=entry.name,
                    days_remaining=entry.days_of_supply,
                )
            )
    return items


def compute_stale_dismissal_keys(
    dismissals: list[DismissedNotification],
    active_keys: set[tuple[uuid.UUID, TriggerType]],
) -> set[tuple[uuid.UUID, str]]:
    """Return the (entry, trigger) keys of dismissals whose condition has cleared.

    Args:
        dismissals (list[DismissedNotification]): The user's dismissal rows.
        active_keys (set[tuple[uuid.UUID, TriggerType]]): Keys of currently-active alerts.

    Returns:
        set[tuple[uuid.UUID, str]]: Dismissal keys with no matching active alert.
    """
    return {
        (dismissal.cabinet_entry_id, dismissal.trigger_type)
        for dismissal in dismissals
        if (dismissal.cabinet_entry_id, TriggerType(dismissal.trigger_type))
        not in active_keys
    }


async def insert_dismissal(
    session: AsyncSession,
    user_id: uuid.UUID,
    request: DismissRequest,
) -> None:
    """Record a dismissal for the given entry/trigger, idempotently.

    Args:
        session (AsyncSession): Active async database session.
        user_id (uuid.UUID): Authenticated user's UUID.
        request (DismissRequest): The entry and trigger type being dismissed.

    Raises:
        DismissalEntryNotFoundError: If the referenced cabinet entry does not exist.
        NotificationsDatabaseError: If the insert fails.
    """
    await crud.insert_dismissal(
        session=session,
        user_id=user_id,
        cabinet_entry_id=request.cabinet_entry_id,
        trigger_type=request.trigger_type.value,
    )


async def delete_stale_dismissals(
    session: AsyncSession,
    user_id: uuid.UUID,
    stale_keys: set[tuple[uuid.UUID, str]],
) -> None:
    """Garbage-collect dismissals whose condition has cleared.

    Args:
        session (AsyncSession): Active async database session.
        user_id (uuid.UUID): Authenticated user's UUID.
        stale_keys (set[tuple[uuid.UUID, str]]): Non-empty set of stale
            (cabinet_entry_id, trigger_type) keys to delete.

    Raises:
        NotificationsDatabaseError: If the delete fails.
    """
    await crud.delete_stale_dismissals(
        session=session, user_id=user_id, stale_keys=stale_keys
    )
