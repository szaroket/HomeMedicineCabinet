"""Cabinet service: pure domain logic and (future) DB-backed orchestration."""

from datetime import date, timedelta
from enum import StrEnum
from typing import NamedTuple


class Status(StrEnum):
    """Expiry status values for a cabinet entry."""

    VALID = "valid"
    EXPIRING = "expiring"
    EXPIRED = "expired"


class TabletPool(NamedTuple):
    """Normalized tablet pool: how many packages and how many tablets in the last one."""

    package_count: int
    partial_tablet_count: int | None


def total_tablets(
    package_count: int,
    partial_tablet_count: int | None,
    tablets_per_package: int,
) -> int:
    """Compute total tablet count for a tablet-based entry.

    Args:
        package_count: Number of full (or last partial) packages.
        partial_tablet_count: Tablets remaining in the last package, or None for full.
        tablets_per_package: Number of tablets in a full package.

    Returns:
        Total number of tablets across all packages.
    """
    if partial_tablet_count is not None:
        return (package_count - 1) * tablets_per_package + partial_tablet_count
    return package_count * tablets_per_package


def normalize_tablet_pool(
    total: int,
    tablets_per_package: int,
) -> TabletPool:
    """Convert a raw tablet count back to a normalized TabletPool.

    Args:
        total: Total number of tablets.
        tablets_per_package: Number of tablets in a full package.

    Returns:
        TabletPool with partial_tablet_count=None when total divides evenly.
    """
    if total % tablets_per_package == 0:
        return TabletPool(total // tablets_per_package, None)
    return TabletPool(total // tablets_per_package + 1, total % tablets_per_package)


def merge_tablet_entry(
    existing_package_count: int,
    existing_partial_tablet_count: int | None,
    new_package_count: int,
    new_partial_tablet_count: int | None,
    tablets_per_package: int,
) -> TabletPool:
    """Merge two tablet-based cabinet entries into a normalized TabletPool.

    Args:
        existing_package_count: Package count of the existing entry.
        existing_partial_tablet_count: Partial tablet count of the existing entry.
        new_package_count: Package count being added.
        new_partial_tablet_count: Partial tablet count being added.
        tablets_per_package: Tablets per full package.

    Returns:
        Normalized TabletPool after merging.
    """
    total_existing = total_tablets(
        existing_package_count, existing_partial_tablet_count, tablets_per_package
    )
    total_new = total_tablets(
        new_package_count, new_partial_tablet_count, tablets_per_package
    )
    return normalize_tablet_pool(total_existing + total_new, tablets_per_package)


def merge_non_tablet_entry(
    existing_packages: int,
    new_packages: int,
) -> int:
    """Merge two non-tablet cabinet entries by summing package counts.

    Args:
        existing_packages: Package count of the existing entry.
        new_packages: Package count being added.

    Returns:
        Combined package count.
    """
    return existing_packages + new_packages


def classify_status(
    expiry_date: date,
    today: date,
    expiry_threshold_days: int,
) -> str:
    """Classify the expiry status of a cabinet entry.

    Args:
        expiry_date: The entry's expiry date (calendar date, UTC-relative).
        today: The reference date (UTC today).
        expiry_threshold_days: Days ahead that triggers "expiring" status.

    Returns:
        One of Status.EXPIRED, Status.EXPIRING, or Status.VALID.
    """
    if expiry_date < today:
        return Status.EXPIRED
    if expiry_date <= today + timedelta(days=expiry_threshold_days):
        return Status.EXPIRING
    return Status.VALID
