"""Unit tests for cabinet service layer: pure domain logic and add_entry orchestration."""

from datetime import date, timedelta
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from sqlalchemy.exc import IntegrityError

from app.api.v1.cabinet.models import CabinetEntry
from app.api.v1.cabinet.schemas import AddEntryResult
from app.api.v1.cabinet.service import (
    Status,
    TabletPool,
    add_entry,
    classify_status,
    list_entries,
    merge_non_tablet_entry,
    merge_tablet_entry,
    normalize_tablet_pool,
    total_tablets,
)
from app.api.v1.medicines.models import MedicationRegistry
from app.utilities.errors import (
    CabinetInvariantError,
    InvalidPartialTabletCountError,
    MedicationNotFoundError,
)

# ---------------------------------------------------------------------------
# total_tablets
# ---------------------------------------------------------------------------


class TestTotalTablets:
    @pytest.mark.parametrize(
        ("package_count", "partial_tablet_count", "tablets_per_package", "expected"),
        [
            (3, None, 20, 60),
            (1, None, 20, 20),
            (2, 5, 20, 25),  # 1 full + 5 tablets in second package → 25
            (1, 10, 20, 10),  # single package, partially used
            (3, 7, 20, 47),  # 2*20 + 7
        ],
    )
    def test_total_tablets(
        self, package_count, partial_tablet_count, tablets_per_package, expected
    ):
        assert (
            total_tablets(
                package_count=package_count,
                partial_tablet_count=partial_tablet_count,
                tablets_per_package=tablets_per_package,
            )
            == expected
        )


# ---------------------------------------------------------------------------
# normalize_tablet_pool
# ---------------------------------------------------------------------------


class TestNormalizeTabletPool:
    @pytest.mark.parametrize(
        ("total", "tablets_per_package", "expected"),
        [
            (40, 20, TabletPool(2, None)),  # even divide clears partial
            (25, 20, TabletPool(2, 5)),  # remainder produces partial
            (5, 20, TabletPool(1, 5)),  # less than one package
            (20, 20, TabletPool(1, None)),  # exactly one package
            (200, 20, TabletPool(10, None)),  # large even
            (201, 20, TabletPool(11, 1)),  # large with remainder
        ],
    )
    def test_normalize_tablet_pool(self, total, tablets_per_package, expected):
        assert (
            normalize_tablet_pool(
                total=total,
                tablets_per_package=tablets_per_package,
            )
            == expected
        )


# ---------------------------------------------------------------------------
# merge_tablet_entry
# ---------------------------------------------------------------------------


class TestMergeTabletEntry:
    @pytest.mark.parametrize(
        (
            "existing_package_count",
            "existing_partial_tablet_count",
            "new_package_count",
            "new_partial_tablet_count",
            "tablets_per_package",
            "expected",
        ),
        [
            # two full packages → even result
            (1, None, 1, None, 20, TabletPool(2, None)),
            # partial on new side only: 20+5=25 → 2 pkg partial 5
            (1, None, 1, 5, 20, TabletPool(2, 5)),
            # partial on existing side only: 5+20=25 → 2 pkg partial 5
            (1, 5, 1, None, 20, TabletPool(2, 5)),
            # partial on both, even result: 10+10=20 → 1 full pkg
            (1, 10, 1, 10, 20, TabletPool(1, None)),
            # partial on both, remainder: 15+15=30 → 2 pkg partial 10
            (1, 15, 1, 15, 20, TabletPool(2, 10)),
            # multi-package: 60+27=87 → 5 pkg partial 7
            (3, None, 2, 7, 20, TabletPool(5, 7)),
            # worked example from plan: 20+5=25 → 2 pkg partial 5
            (1, None, 1, 5, 20, TabletPool(2, 5)),
        ],
    )
    def test_merge_tablet_entry(
        self,
        existing_package_count,
        existing_partial_tablet_count,
        new_package_count,
        new_partial_tablet_count,
        tablets_per_package,
        expected,
    ):
        assert (
            merge_tablet_entry(
                existing_package_count=existing_package_count,
                existing_partial_tablet_count=existing_partial_tablet_count,
                new_package_count=new_package_count,
                new_partial_tablet_count=new_partial_tablet_count,
                tablets_per_package=tablets_per_package,
            )
            == expected
        )


# ---------------------------------------------------------------------------
# merge_non_tablet_entry
# ---------------------------------------------------------------------------


class TestMergeNonTabletEntry:
    @pytest.mark.parametrize(
        ("existing_packages", "new_packages", "expected"),
        [
            (3, 2, 5),
            (1, 1, 2),
            (100, 50, 150),
        ],
    )
    def test_merge_non_tablet_entry(self, existing_packages, new_packages, expected):
        assert (
            merge_non_tablet_entry(
                existing_packages=existing_packages,
                new_packages=new_packages,
            )
            == expected
        )


# ---------------------------------------------------------------------------
# classify_status
# ---------------------------------------------------------------------------


class TestClassifyStatus:
    TODAY = date(2026, 6, 9)
    THRESHOLD = 30

    @pytest.mark.parametrize(
        ("expiry_date", "today", "expiry_threshold_days", "expected"),
        [
            # expired
            (TODAY - timedelta(days=1), TODAY, THRESHOLD, Status.EXPIRED),
            # expiring: today
            (TODAY, TODAY, THRESHOLD, Status.EXPIRING),
            # expiring: exactly at threshold edge
            (TODAY + timedelta(days=THRESHOLD), TODAY, THRESHOLD, Status.EXPIRING),
            # expiring: one day before expiry
            (TODAY + timedelta(days=1), TODAY, THRESHOLD, Status.EXPIRING),
            # valid: one day past threshold
            (TODAY + timedelta(days=THRESHOLD + 1), TODAY, THRESHOLD, Status.VALID),
            # valid: far future
            (TODAY + timedelta(days=365), TODAY, THRESHOLD, Status.VALID),
            # zero threshold: today is expiring
            (TODAY, TODAY, 0, Status.EXPIRING),
            # zero threshold: tomorrow is valid
            (TODAY + timedelta(days=1), TODAY, 0, Status.VALID),
        ],
    )
    def test_classify_status(self, expiry_date, today, expiry_threshold_days, expected):
        assert (
            classify_status(
                expiry_date=expiry_date,
                today=today,
                expiry_threshold_days=expiry_threshold_days,
            )
            == expected
        )


# ---------------------------------------------------------------------------
# add_entry orchestration
# ---------------------------------------------------------------------------

_USER_ID = uuid4()
_REGISTRY_ID = uuid4()
_ENTRY_ID = uuid4()
_EXPIRY = date(2027, 6, 1)
_TPP = 20


def _make_variant(
    *,
    is_tablet_based: bool = True,
    capacity: Decimal | None = Decimal(_TPP),
) -> MagicMock:
    v = MagicMock(spec=MedicationRegistry)
    v.id = _REGISTRY_ID
    v.is_tablet_based = is_tablet_based
    v.capacity = capacity
    v.name = "Apap"
    v.strength = "500 mg"
    v.pharmaceutical_form = "tabletki"
    v.capacity_unit = "tabl."
    v.route_of_administration = "doustna"
    v.leaflet_url = "https://example.com/leaflet"
    v.specification_url = "https://example.com/spec"
    return v


def _make_entry(package_count: int = 1, partial: int | None = None) -> MagicMock:
    e = MagicMock(spec=CabinetEntry)
    e.id = uuid4()
    e.user_id = _USER_ID
    e.medication_registry_id = _REGISTRY_ID
    e.package_count = package_count
    e.partial_tablet_count = partial
    e.expiry_date = _EXPIRY
    return e


@pytest.fixture
def mock_crud(mocker):
    """Patch the entire cabinet crud module used by service."""
    return mocker.patch("app.api.v1.cabinet.service.crud", autospec=True)


class TestAddEntryFreshInsert:
    async def test_tablet_fresh_insert_returns_merged_false(
        self, mock_session: AsyncMock, mock_crud
    ):
        variant = _make_variant()
        entry = _make_entry(package_count=2, partial=5)
        mock_crud.get_registry_by_id = AsyncMock(return_value=variant)
        mock_crud.find_entry = AsyncMock(return_value=None)
        mock_crud.insert_entry = AsyncMock(return_value=entry)

        result = await add_entry(
            session=mock_session,
            user_id=_USER_ID,
            medication_registry_id=_REGISTRY_ID,
            package_count=2,
            partial_tablet_count=5,
            expiry_date=_EXPIRY,
        )

        assert isinstance(result, AddEntryResult)
        assert result.merged is False
        assert result.merge_summary is None
        assert result.entry.package_count == 2
        assert result.entry.partial_tablet_count == 5
        assert result.entry.total_tablets == 25  # (2-1)*20 + 5

    async def test_non_tablet_fresh_insert_has_null_total_tablets(
        self, mock_session: AsyncMock, mock_crud
    ):
        variant = _make_variant(is_tablet_based=False, capacity=None)
        entry = _make_entry(package_count=3)
        mock_crud.get_registry_by_id = AsyncMock(return_value=variant)
        mock_crud.find_entry = AsyncMock(return_value=None)
        mock_crud.insert_entry = AsyncMock(return_value=entry)

        result = await add_entry(
            session=mock_session,
            user_id=_USER_ID,
            medication_registry_id=_REGISTRY_ID,
            package_count=3,
            partial_tablet_count=None,
            expiry_date=_EXPIRY,
        )

        assert result.merged is False
        assert result.entry.total_tablets is None


class TestAddEntryMerge:
    async def test_tablet_merge_returns_merged_true_with_summary(
        self, mock_session: AsyncMock, mock_crud
    ):
        variant = _make_variant()
        existing = _make_entry(package_count=1, partial=None)  # 20 tablets
        updated = _make_entry(package_count=2, partial=5)  # 45 tablets after merge
        mock_crud.get_registry_by_id = AsyncMock(return_value=variant)
        mock_crud.find_entry = AsyncMock(return_value=existing)
        mock_crud.update_entry_counts = AsyncMock(return_value=updated)

        result = await add_entry(
            session=mock_session,
            user_id=_USER_ID,
            medication_registry_id=_REGISTRY_ID,
            package_count=1,
            partial_tablet_count=5,
            expiry_date=_EXPIRY,
        )

        assert result.merged is True
        assert result.merge_summary is not None
        assert result.merge_summary.previous_total_tablets == 20
        assert result.merge_summary.added_total_tablets == 5  # (1-1)*20+5
        assert result.merge_summary.new_total_tablets == 25

    async def test_non_tablet_merge_sums_package_counts(
        self, mock_session: AsyncMock, mock_crud
    ):
        variant = _make_variant(is_tablet_based=False, capacity=None)
        existing = _make_entry(package_count=3)
        updated = _make_entry(package_count=5)
        mock_crud.get_registry_by_id = AsyncMock(return_value=variant)
        mock_crud.find_entry = AsyncMock(return_value=existing)
        mock_crud.update_entry_counts = AsyncMock(return_value=updated)

        result = await add_entry(
            session=mock_session,
            user_id=_USER_ID,
            medication_registry_id=_REGISTRY_ID,
            package_count=2,
            partial_tablet_count=None,
            expiry_date=_EXPIRY,
        )

        assert result.merged is True
        assert result.entry.package_count == 5
        assert result.merge_summary.previous_package_count == 3


class TestAddEntryRaceCondition:
    async def test_integrity_error_falls_through_to_merge(
        self, mock_session: AsyncMock, mock_crud
    ):
        variant = _make_variant()
        existing = _make_entry(package_count=1)
        updated = _make_entry(package_count=2)
        mock_crud.get_registry_by_id = AsyncMock(return_value=variant)
        mock_crud.find_entry = AsyncMock(side_effect=[None, existing])
        mock_crud.insert_entry = AsyncMock(
            side_effect=IntegrityError("unique", {}, Exception())
        )
        mock_crud.update_entry_counts = AsyncMock(return_value=updated)

        result = await add_entry(
            session=mock_session,
            user_id=_USER_ID,
            medication_registry_id=_REGISTRY_ID,
            package_count=1,
            partial_tablet_count=None,
            expiry_date=_EXPIRY,
        )

        assert result.merged is True

    async def test_integrity_error_with_missing_row_raises_invariant_error(
        self, mock_session: AsyncMock, mock_crud
    ):
        variant = _make_variant()
        mock_crud.get_registry_by_id = AsyncMock(return_value=variant)
        mock_crud.find_entry = AsyncMock(return_value=None)
        mock_crud.insert_entry = AsyncMock(
            side_effect=IntegrityError("unique", {}, Exception())
        )

        with pytest.raises(CabinetInvariantError):
            await add_entry(
                session=mock_session,
                user_id=_USER_ID,
                medication_registry_id=_REGISTRY_ID,
                package_count=1,
                partial_tablet_count=None,
                expiry_date=_EXPIRY,
            )


class TestAddEntryValidation:
    async def test_unknown_registry_id_raises_not_found(
        self, mock_session: AsyncMock, mock_crud
    ):
        mock_crud.get_registry_by_id = AsyncMock(return_value=None)

        with pytest.raises(MedicationNotFoundError):
            await add_entry(
                session=mock_session,
                user_id=_USER_ID,
                medication_registry_id=_REGISTRY_ID,
                package_count=1,
                partial_tablet_count=None,
                expiry_date=_EXPIRY,
            )

    @pytest.mark.parametrize("partial", [0, 20, 21])
    async def test_out_of_range_partial_raises_error(
        self, partial, mock_session: AsyncMock, mock_crud
    ):
        mock_crud.get_registry_by_id = AsyncMock(return_value=_make_variant())

        with pytest.raises(InvalidPartialTabletCountError):
            await add_entry(
                session=mock_session,
                user_id=_USER_ID,
                medication_registry_id=_REGISTRY_ID,
                package_count=1,
                partial_tablet_count=partial,
                expiry_date=_EXPIRY,
            )

    async def test_partial_on_non_tablet_raises_error(
        self, mock_session: AsyncMock, mock_crud
    ):
        mock_crud.get_registry_by_id = AsyncMock(
            return_value=_make_variant(is_tablet_based=False, capacity=None)
        )

        with pytest.raises(InvalidPartialTabletCountError):
            await add_entry(
                session=mock_session,
                user_id=_USER_ID,
                medication_registry_id=_REGISTRY_ID,
                package_count=1,
                partial_tablet_count=3,
                expiry_date=_EXPIRY,
            )

    @pytest.mark.parametrize(
        "capacity", [None, Decimal(0), Decimal("-1")], ids=["null", "zero", "negative"]
    )
    async def test_invalid_capacity_on_tablet_variant_raises_invariant_error(
        self, mock_session: AsyncMock, mock_crud, capacity: Decimal | None
    ):
        # A non-positive capacity must be rejected like NULL: tpp=0 would drive
        # normalize_tablet_pool into a divide-by-zero on the merge path.
        mock_crud.get_registry_by_id = AsyncMock(
            return_value=_make_variant(is_tablet_based=True, capacity=capacity)
        )

        with pytest.raises(CabinetInvariantError):
            await add_entry(
                session=mock_session,
                user_id=_USER_ID,
                medication_registry_id=_REGISTRY_ID,
                package_count=1,
                partial_tablet_count=None,
                expiry_date=_EXPIRY,
            )


# ---------------------------------------------------------------------------
# list_entries
# ---------------------------------------------------------------------------


def _make_real_entry(
    package_count: int = 1,
    partial_tablet_count: int | None = None,
    expiry_date: date = _EXPIRY,
) -> CabinetEntry:
    return CabinetEntry(
        id=_ENTRY_ID,
        user_id=_USER_ID,
        medication_registry_id=_REGISTRY_ID,
        package_count=package_count,
        partial_tablet_count=partial_tablet_count,
        expiry_date=expiry_date,
    )


@pytest.fixture
def mock_list_crud(mocker):
    return mocker.patch("app.api.v1.cabinet.service.crud", autospec=True)


class TestListEntries:
    async def test_returns_cabinet_entry_out_with_status(
        self, mock_session: AsyncMock, mock_list_crud
    ):
        today = date.today()
        future = today + timedelta(days=60)
        entry = _make_real_entry(
            package_count=2, partial_tablet_count=5, expiry_date=future
        )
        variant = _make_variant(is_tablet_based=True, capacity=Decimal(20))
        mock_list_crud.list_entries = AsyncMock(return_value=[(entry, variant)])

        result = await list_entries(
            session=mock_session,
            user_id=_USER_ID,
            expiry_threshold_days=30,
        )

        assert len(result) == 1
        assert result[0].status == Status.VALID
        assert result[0].total_tablets == 25  # (2-1)*20 + 5
        assert result[0].name == variant.name
        assert result[0].route_of_administration == variant.route_of_administration
        assert result[0].leaflet_url == variant.leaflet_url
        assert result[0].specification_url == variant.specification_url

    async def test_expired_entry_returns_expired_status(
        self, mock_session: AsyncMock, mock_list_crud
    ):
        past = date.today() - timedelta(days=1)
        entry = _make_real_entry(expiry_date=past)
        variant = _make_variant(is_tablet_based=False)
        mock_list_crud.list_entries = AsyncMock(return_value=[(entry, variant)])

        result = await list_entries(
            session=mock_session, user_id=_USER_ID, expiry_threshold_days=30
        )

        assert result[0].status == Status.EXPIRED

    async def test_expiring_entry_returns_expiring_status(
        self, mock_session: AsyncMock, mock_list_crud
    ):
        soon = date.today() + timedelta(days=10)
        entry = _make_real_entry(expiry_date=soon)
        variant = _make_variant(is_tablet_based=False)
        mock_list_crud.list_entries = AsyncMock(return_value=[(entry, variant)])

        result = await list_entries(
            session=mock_session, user_id=_USER_ID, expiry_threshold_days=30
        )

        assert result[0].status == Status.EXPIRING

    async def test_non_tablet_variant_has_none_total_tablets(
        self, mock_session: AsyncMock, mock_list_crud
    ):
        entry = _make_real_entry(package_count=3)
        variant = _make_variant(is_tablet_based=False)
        mock_list_crud.list_entries = AsyncMock(return_value=[(entry, variant)])

        result = await list_entries(
            session=mock_session, user_id=_USER_ID, expiry_threshold_days=30
        )

        assert result[0].total_tablets is None
        assert result[0].package_count == 3

    async def test_empty_cabinet_returns_empty_list(
        self, mock_session: AsyncMock, mock_list_crud
    ):
        mock_list_crud.list_entries = AsyncMock(return_value=[])

        result = await list_entries(
            session=mock_session, user_id=_USER_ID, expiry_threshold_days=30
        )

        assert result == []
