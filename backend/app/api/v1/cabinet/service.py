"""Cabinet service: pure domain logic and DB-backed orchestration."""

import logging
import uuid
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from enum import StrEnum
from typing import NamedTuple, cast

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.cabinet import crud
from app.api.v1.cabinet.models import CabinetEntry
from app.api.v1.cabinet.schemas import (
    AddEntryOut,
    AddEntryResult,
    CabinetEntryOut,
    CabinetPageOut,
    MergeSummary,
)
from app.api.v1.medicines.models import MedicationRegistry
from app.utilities.common import build_tsquery
from app.utilities.const import DEFAULT_MIN_PACKAGE_COUNT
from app.utilities.errors import (
    CabinetInvariantError,
    EntryNotFoundError,
    InvalidPartialTabletCountError,
    MedicationNotFoundError,
)

logger = logging.getLogger("app.cabinet.service")


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
        package_count (int): Number of full (or last partial) packages.
        partial_tablet_count (int | None): Tablets remaining in the last package, or None for full.
        tablets_per_package (int): Number of tablets in a full package.

    Returns:
        int: Total number of tablets across all packages.
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
        total (int): Total number of tablets.
        tablets_per_package (int): Number of tablets in a full package.

    Returns:
        TabletPool: with partial_tablet_count=None when total divides evenly.
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
        existing_package_count (int): Package count of the existing entry.
        existing_partial_tablet_count (int | None): Partial tablet count of the existing entry.
        new_package_count (int): Package count being added.
        new_partial_tablet_count (int | None): Partial tablet count being added.
        tablets_per_package (int): Tablets per full package.

    Returns:
        TabletPool: Normalized TabletPool after merging.
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
        existing_packages (int): Package count of the existing entry.
        new_packages (int): Package count being added.

    Returns:
        int: Combined package count.
    """
    return existing_packages + new_packages


def is_below_minimum(
    is_important: bool,
    package_count: int,
    min_package_count: int,
) -> bool:
    """Return True when an important entry has fewer packages than the global minimum.

    Args:
        is_important (bool): Whether the entry is marked important.
        package_count (int): Current package count for the entry.
        min_package_count (int): User's global minimum package count.

    Returns:
        bool: True only when is_important is True and package_count < min_package_count.
    """
    return is_important and package_count < min_package_count


def classify_status(
    expiry_date: date,
    today: date,
    expiry_threshold_days: int,
) -> str:
    """Classify the expiry status of a cabinet entry.

    Args:
        expiry_date (date): The entry's expiry date (calendar date, UTC-relative).
        today (date): The reference date (UTC today).
        expiry_threshold_days (int): Days ahead that triggers "expiring" status.

    Returns:
        str: One of Status.EXPIRED, Status.EXPIRING, or Status.VALID.
    """
    if expiry_date < today:
        return Status.EXPIRED
    if expiry_date <= today + timedelta(days=expiry_threshold_days):
        return Status.EXPIRING
    return Status.VALID


def _tablet_capacity_invalid(variant: MedicationRegistry) -> bool:
    """Return True when a tablet-based variant has a missing or non-positive capacity.

    Tablet-based registry rows must carry a positive integer capacity (tablets per
    package). A NULL or non-positive capacity is a data-integrity breach: it cannot
    yield a usable tablets-per-package and would drive tablet math toward a divide
    -by-zero. Centralized so the read and write paths classify the breach identically.

    Args:
        variant (MedicationRegistry): The MedicationRegistry row for the selected variant.

    Returns:
        bool: True if the variant is tablet-based but its capacity is None or <= 0.
    """
    return variant.is_tablet_based and (
        variant.capacity is None or variant.capacity <= 0
    )


def _map_row_to_entry_out(
    entry: CabinetEntry,
    variant: MedicationRegistry,
    today: date,
    expiry_threshold_days: int,
    min_package_count: int = DEFAULT_MIN_PACKAGE_COUNT,
) -> CabinetEntryOut:
    """Map a (CabinetEntry, MedicationRegistry) row to CabinetEntryOut.

    Args:
        entry (CabinetEntry): The cabinet entry row.
        variant (MedicationRegistry): The joined registry row.
        today (date): Reference date for status classification.
        expiry_threshold_days (int): Days ahead that triggers "expiring" status.
        min_package_count (int): User's global minimum package count for below-minimum signal.

    Returns:
        CabinetEntryOut: Populated CabinetEntryOut.
    """
    capacity_invalid = _tablet_capacity_invalid(variant)
    if capacity_invalid:
        logger.warning(
            "Tablet-based registry row %s has invalid capacity %r; "
            "total_tablets left None for cabinet entry %s",
            variant.id,
            variant.capacity,
            entry.id,
        )
    tpp = None
    if variant.is_tablet_based and not capacity_invalid:
        tpp = int(cast(Decimal, variant.capacity))
    return CabinetEntryOut(
        id=entry.id,
        name=variant.name,
        strength=variant.strength,
        pharmaceutical_form=variant.pharmaceutical_form,
        capacity=variant.capacity,
        capacity_unit=variant.capacity_unit,
        is_tablet_based=variant.is_tablet_based,
        package_count=entry.package_count,
        partial_tablet_count=entry.partial_tablet_count,
        expiry_date=entry.expiry_date,
        total_tablets=_computed_total(entry, tpp),
        status=classify_status(entry.expiry_date, today, expiry_threshold_days),
        is_important=entry.is_important,
        below_minimum=is_below_minimum(
            entry.is_important, entry.package_count, min_package_count
        ),
        active_ingredient=variant.active_ingredient,
        route_of_administration=variant.route_of_administration,
        leaflet_url=variant.leaflet_url,
        specification_url=variant.specification_url,
    )


async def list_entries(
    session: AsyncSession,
    user_id: uuid.UUID,
    expiry_threshold_days: int,
    status: str | None = None,
    search: str | None = None,
    order: str = "asc",
    page: int = 1,
    page_size: int = 20,
    min_package_count: int = DEFAULT_MIN_PACKAGE_COUNT,
    category: str | None = None,
    below_minimum: bool | None = None,
) -> CabinetPageOut:
    """Return a paginated page of cabinet entries with computed expiry status.

    Args:
        session (AsyncSession): Active async database session.
        user_id (uuid.UUID): Authenticated user's UUID.
        expiry_threshold_days (int): Days ahead that triggers "expiring" status.
        status (str | None): Optional status filter ("valid", "expiring", "expired").
        search (str | None): Optional raw search string (name or active ingredient).
        order (str): Sort direction for medication name ("asc" or "desc").
        page (int): 1-based page number.
        page_size (int): Number of items per page (20, 50, or 100).
        min_package_count (int): User's global minimum package count for below-minimum signal.
        category (str | None): Optional category filter ("important" filters to important entries).
        below_minimum (bool | None): When True, filter to important entries below the package minimum.

    Returns:
        CabinetPageOut: with items, total, page, and page_size.
    """
    today = datetime.now(timezone.utc).date()
    offset = (page - 1) * page_size

    rows, total = await crud.list_entries(
        session=session,
        user_id=user_id,
        today=today,
        threshold=expiry_threshold_days,
        status=status,
        tsquery=build_tsquery(search) if search is not None else None,
        order=order,
        limit=page_size,
        offset=offset,
        category=category,
        below_minimum=below_minimum,
        min_package_count=min_package_count,
    )
    items = [
        _map_row_to_entry_out(
            entry=entry,
            variant=variant,
            today=today,
            expiry_threshold_days=expiry_threshold_days,
            min_package_count=min_package_count,
        )
        for entry, variant in rows
    ]
    return CabinetPageOut(items=items, total=total, page=page, page_size=page_size)


async def _get_variant_or_raise(
    session: AsyncSession,
    medication_registry_id: uuid.UUID,
) -> MedicationRegistry:
    """Fetch a registry variant by ID or raise MedicationNotFoundError.

    Args:
        session (AsyncSession): Active async database session.
        medication_registry_id (uuid.UUID): UUID of the registry row to look up.

    Returns:
        MedicationRegistry: The MedicationRegistry row.

    Raises:
        MedicationNotFoundError: When no row exists for the given ID.
    """
    variant = await crud.get_registry_by_id(session, medication_registry_id)
    if variant is None:
        raise MedicationNotFoundError()
    return variant


def _validate_and_get_tpp(
    variant: MedicationRegistry,
    partial_tablet_count: int | None,
) -> int | None:
    """Validate partial_tablet_count against the variant and return tablets-per-package.

    Args:
        variant (MedicationRegistry): The MedicationRegistry row for the selected variant.
        partial_tablet_count (int | None): Tablets in the last package supplied by the caller.

    Returns:
        int | None: Tablets per package for tablet-based variants, None otherwise.

    Raises:
        CabinetInvariantError: When a tablet-based variant has a missing or
            non-positive capacity (data-integrity breach).
        InvalidPartialTabletCountError: When partial_tablet_count is supplied for
            a non-tablet variant or is outside the valid range 1…tpp-1.
    """
    if variant.is_tablet_based:
        if _tablet_capacity_invalid(variant):
            raise CabinetInvariantError(
                f"Registry invariant violated: tablet-based row {variant.id} "
                f"has invalid capacity {variant.capacity!r}"
            )
        tpp = int(cast(Decimal, variant.capacity))
        if partial_tablet_count is not None and not (
            1 <= partial_tablet_count <= tpp - 1
        ):
            raise InvalidPartialTabletCountError(
                f"partial_tablet_count must be between 1 and {tpp - 1} for this variant."
            )
        return tpp
    if partial_tablet_count is not None:
        raise InvalidPartialTabletCountError(
            "partial_tablet_count is not applicable for non-tablet variants."
        )
    return None


def _computed_total(entry: CabinetEntry, tpp: int | None) -> int | None:
    if tpp is not None:
        return total_tablets(entry.package_count, entry.partial_tablet_count, tpp)
    return None


def _build_add_entry_out(
    entry: CabinetEntry,
    variant: MedicationRegistry,
    tpp: int | None,
) -> AddEntryOut:
    """Assemble an AddEntryOut (no status) from a persisted entry and its variant.

    Args:
        entry (CabinetEntry): The CabinetEntry row (flushed or committed).
        variant (MedicationRegistry): The MedicationRegistry row for display fields.
        tpp (int | None): Tablets per package, or None for non-tablet variants.

    Returns:
        AddEntryOut: Populated AddEntryOut without status.
    """
    return AddEntryOut(
        id=entry.id,
        name=variant.name,
        strength=variant.strength,
        pharmaceutical_form=variant.pharmaceutical_form,
        capacity=variant.capacity,
        capacity_unit=variant.capacity_unit,
        is_tablet_based=variant.is_tablet_based,
        package_count=entry.package_count,
        partial_tablet_count=entry.partial_tablet_count,
        expiry_date=entry.expiry_date,
        total_tablets=_computed_total(entry, tpp),
        is_important=entry.is_important,
    )


async def _insert_with_race_guard(
    session: AsyncSession,
    user_id: uuid.UUID,
    medication_registry_id: uuid.UUID,
    package_count: int,
    partial_tablet_count: int | None,
    expiry_date: date,
    is_important: bool = False,
) -> CabinetEntry | None:
    """Insert a new cabinet entry, returning None on a concurrent-insert race.

    On ``IntegrityError`` (duplicate unique key from a concurrent POST), rolls
    back the failed insert and returns ``None`` so the caller can fall through
    to the merge path.

    Args:
        session (AsyncSession): Active async database session.
        user_id (uuid.UUID): Authenticated user's UUID.
        medication_registry_id (uuid.UUID): UUID of the selected registry variant.
        package_count (int): Number of packages to insert.
        partial_tablet_count (int | None): Tablets in the last package, or None.
        expiry_date (date): Expiry date for the entry.
        is_important (bool): Whether the entry is marked important.

    Returns:
        CabinetEntry | None: The newly created CabinetEntry, or None if a race condition was detected.
    """
    try:
        return await crud.insert_entry(
            session,
            user_id,
            medication_registry_id,
            package_count,
            partial_tablet_count,
            expiry_date,
            is_important=is_important,
        )
    except IntegrityError:
        return None


async def _dedup_or_insert(
    *,
    session: AsyncSession,
    user_id: uuid.UUID,
    medication_registry_id: uuid.UUID,
    package_count: int,
    partial_tablet_count: int | None,
    expiry_date: date,
    variant: MedicationRegistry,
    tpp: int | None,
    is_important: bool = False,
) -> AddEntryResult:
    """Check for a duplicate entry and merge, or insert fresh (with race guard).

    Looks up the dedup key. On a hit, delegates to ``_merge_and_commit``. On a
    miss, inserts; if a concurrent request wins the race and triggers an
    ``IntegrityError``, rolls back and falls through to the merge path.

    Args:
        session (AsyncSession): Active async database session.
        user_id (uuid.UUID): Authenticated user's UUID.
        medication_registry_id (uuid.UUID): UUID of the selected registry variant.
        package_count (int): Number of packages to add.
        partial_tablet_count (int | None): Tablets in the last package, or None.
        expiry_date (date): Expiry date for the entry.
        variant (MedicationRegistry): Already-fetched MedicationRegistry row.
        tpp (int | None): Tablets per package, or None for non-tablet variants.
        is_important (bool): Whether the incoming add marks this entry as important.

    Returns:
        AddEntryResult: with merged=False for a fresh insert, merged=True on merge.

    Raises:
        CabinetInvariantError: If an IntegrityError occurs but the row is missing.
    """
    existing = await crud.find_entry(
        session, user_id, medication_registry_id, expiry_date
    )
    if existing is not None:
        return await _merge_and_commit(
            session=session,
            existing=existing,
            new_package_count=package_count,
            new_partial=partial_tablet_count,
            variant=variant,
            tpp=tpp,
            is_important=is_important,
        )

    entry = await _insert_with_race_guard(
        session,
        user_id,
        medication_registry_id,
        package_count,
        partial_tablet_count,
        expiry_date,
        is_important=is_important,
    )
    if entry is None:
        existing = await crud.find_entry(
            session, user_id, medication_registry_id, expiry_date
        )
        if existing is None:
            raise CabinetInvariantError(
                "Race-condition insert failed but row not found"
            )
        return await _merge_and_commit(
            session=session,
            existing=existing,
            new_package_count=package_count,
            new_partial=partial_tablet_count,
            variant=variant,
            tpp=tpp,
            is_important=is_important,
        )

    return AddEntryResult(
        merged=False,
        entry=_build_add_entry_out(entry, variant, tpp),
        merge_summary=None,
    )


async def add_entry(
    session: AsyncSession,
    user_id: uuid.UUID,
    medication_registry_id: uuid.UUID,
    package_count: int,
    partial_tablet_count: int | None,
    expiry_date: date,
    is_important: bool = False,
) -> AddEntryResult:
    """Validate, dedup/merge, persist, and return the add result.

    Orchestrates the full add flow: looks up the registry variant, validates
    tablet/non-tablet constraints, checks for an existing entry with the same
    dedup key, merges (FR-010) or inserts, computes status, and returns an
    ``AddEntryResult`` envelope.

    On a concurrent-add race (two simultaneous POSTs with the same dedup key),
    the ``IntegrityError`` from the failed insert is caught, the transaction is
    rolled back, and the winning row is re-fetched so the same merge path runs.

    On merge, importance is OR'd: an entry already marked important stays
    important; a new add with is_important=True marks a previously unimportant
    entry important (FR-010 addendum).

    Args:
        session (AsyncSession): Active async database session.
        user_id (uuid.UUID): Authenticated user's UUID.
        medication_registry_id (uuid.UUID): UUID of the selected registry variant.
        package_count (int): Number of packages to add (>= 1).
        partial_tablet_count (int | None): Tablets in the last package, or None.
        expiry_date (date): Expiry date for the entry.
        is_important (bool): Whether the incoming add marks this entry as important.

    Returns:
        AddEntryResult: with merged flag, the resulting entry, and an optional
        MergeSummary.

    Raises:
        MedicationNotFoundError: When the registry variant does not exist.
        InvalidPartialTabletCountError: When partial_tablet_count is supplied
            for a non-tablet variant, or outside the valid range.
    """
    variant = await _get_variant_or_raise(session, medication_registry_id)
    tpp = _validate_and_get_tpp(variant, partial_tablet_count)
    return await _dedup_or_insert(
        session=session,
        user_id=user_id,
        medication_registry_id=medication_registry_id,
        package_count=package_count,
        partial_tablet_count=partial_tablet_count,
        expiry_date=expiry_date,
        variant=variant,
        tpp=tpp,
        is_important=is_important,
    )


async def set_entry_importance(
    session: AsyncSession,
    user_id: uuid.UUID,
    entry_id: uuid.UUID,
    is_important: bool,
    expiry_threshold_days: int,
    min_package_count: int = DEFAULT_MIN_PACKAGE_COUNT,
) -> CabinetEntryOut:
    """Toggle the importance flag on a cabinet entry owned by the user.

    Args:
        session (AsyncSession): Active async database session.
        user_id (uuid.UUID): Authenticated user's UUID.
        entry_id (uuid.UUID): UUID of the cabinet entry to update.
        is_important (bool): New importance flag value.
        expiry_threshold_days (int): Days ahead that triggers "expiring" status.
        min_package_count (int): User's global minimum package count for below-minimum signal.

    Returns:
        CabinetEntryOut: The updated CabinetEntryOut with recomputed status and below_minimum.

    Raises:
        EntryNotFoundError: When the entry does not exist or does not belong to the user.
        MedicationNotFoundError: When the entry's registry variant no longer exists.
        CabinetDatabaseError: When a database operation fails.
    """
    entry = await crud.find_entry_by_id(
        session=session, user_id=user_id, entry_id=entry_id
    )
    if entry is None:
        raise EntryNotFoundError()
    updated_entry = await crud.update_entry_importance(
        session=session, entry=entry, is_important=is_important
    )
    variant = await _get_variant_or_raise(
        session=session, medication_registry_id=entry.medication_registry_id
    )
    today = datetime.now(timezone.utc).date()
    return _map_row_to_entry_out(
        entry=updated_entry,
        variant=variant,
        today=today,
        expiry_threshold_days=expiry_threshold_days,
        min_package_count=min_package_count,
    )


async def _merge_and_commit(
    *,
    session: AsyncSession,
    existing: CabinetEntry,
    new_package_count: int,
    new_partial: int | None,
    variant: MedicationRegistry,
    tpp: int | None,
    is_important: bool = False,
) -> AddEntryResult:
    """Apply FR-010 merge math, persist the update, and return AddEntryResult.

    Args:
        session (AsyncSession): Active async database session.
        existing (CabinetEntry): The existing CabinetEntry to merge into.
        new_package_count (int): Package count of the incoming add.
        new_partial (int | None): Partial tablet count of the incoming add, or None.
        variant (MedicationRegistry): The MedicationRegistry row for display fields.
        tpp (int | None): Tablets per package for tablet-based variants, None otherwise.
        is_important (bool): Importance of the incoming add; OR'd with existing flag.

    Returns:
        AddEntryResult: with merged=True and populated merge_summary.
    """
    prev_pkg = existing.package_count
    prev_partial = existing.partial_tablet_count
    merged_important = existing.is_important or is_important

    if tpp is not None:
        prev_total = total_tablets(prev_pkg, prev_partial, tpp)
        added_total = total_tablets(new_package_count, new_partial, tpp)
        pool = merge_tablet_entry(
            prev_pkg, prev_partial, new_package_count, new_partial, tpp
        )
        new_pkg = pool.package_count
        new_partial_result: int | None = pool.partial_tablet_count
        summary = MergeSummary(
            previous_package_count=prev_pkg,
            previous_partial_tablet_count=prev_partial,
            previous_total_tablets=prev_total,
            added_total_tablets=added_total,
            new_total_tablets=total_tablets(new_pkg, new_partial_result, tpp),
        )
    else:
        new_pkg = merge_non_tablet_entry(prev_pkg, new_package_count)
        new_partial_result = None
        summary = MergeSummary(
            previous_package_count=prev_pkg,
            previous_partial_tablet_count=None,
            previous_total_tablets=None,
            added_total_tablets=None,
            new_total_tablets=None,
        )

    updated = await crud.update_entry_counts(
        session, existing, new_pkg, new_partial_result, is_important=merged_important
    )

    return AddEntryResult(
        merged=True,
        entry=_build_add_entry_out(updated, variant, tpp),
        merge_summary=summary,
    )
