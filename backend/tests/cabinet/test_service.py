"""Unit tests for cabinet service layer: pure domain logic and add_entry orchestration."""

from datetime import date, timedelta
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from pytest_mock import MockerFixture
from sqlalchemy.exc import IntegrityError

from app.api.v1.cabinet.models import CabinetEntry
from app.api.v1.cabinet.schemas import (
    AddEntryResult,
    CabinetPageOut,
    UsageFields,
)
from app.api.v1.cabinet.service import (
    Status,
    TabletPool,
    UsageView,
    add_entry,
    classify_status,
    compute_usage_view,
    daily_consumption_rate,
    days_of_supply_from_rate,
    delete_entry,
    is_below_minimum,
    list_entries,
    merge_non_tablet_entry,
    merge_tablet_entry,
    normalize_tablet_pool,
    set_entry_usage,
    total_tablets,
    validate_usage,
)
from app.api.v1.medicines.models import MedicationRegistry
from app.utilities.errors import (
    CabinetInvariantError,
    EntryNotFoundError,
    InvalidDosageError,
    InvalidPartialTabletCountError,
    MedicationNotFoundError,
)
from app.utilities.types import DosagePeriod

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
            # multi-package partial+partial remainder: 33+49=82 → 5 pkg partial 2
            (2, 13, 3, 9, 20, TabletPool(5, 2)),
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
# SQL status filter ↔ classify_status parity
# ---------------------------------------------------------------------------


def _sql_status(expiry_date: date, today: date, threshold: int) -> str:
    """Mirror the SQL date predicates from crud._build_base_query in Python."""
    if expiry_date < today:
        return "expired"
    if expiry_date <= today + timedelta(days=threshold):
        return "expiring"
    return "valid"


class TestStatusSQLParity:
    """Assert that SQL predicates and classify_status agree on boundary dates."""

    TODAY = date(2026, 6, 15)
    THRESHOLD = 30

    @pytest.mark.parametrize(
        "expiry_date",
        [
            date(2026, 6, 15),  # today → expiring
            date(2026, 7, 15),  # today + threshold → expiring
            date(2026, 7, 16),  # today + threshold + 1 → valid
            date(2026, 6, 14),  # yesterday → expired
        ],
        ids=["today", "today+threshold", "today+threshold+1", "yesterday"],
    )
    def test_parity_at_boundary(self, expiry_date: date):
        sql_result = _sql_status(expiry_date, self.TODAY, self.THRESHOLD)
        py_result = classify_status(expiry_date, self.TODAY, self.THRESHOLD)
        assert sql_result == py_result, (
            f"Mismatch for expiry_date={expiry_date}: SQL={sql_result}, classify_status={py_result}"
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
    v.active_ingredient = "Paracetamolum"
    v.route_of_administration = "doustna"
    v.leaflet_url = "https://example.com/leaflet"
    v.specification_url = "https://example.com/spec"
    return v


def _make_entry(
    package_count: int = 1,
    partial: int | None = None,
    is_important: bool = False,
    is_used: bool = False,
    dosage_times: int | None = None,
    dosage_period: str | None = None,
    dosage_amount: int | None = None,
    dosage_start_date: date | None = None,
    dosage_end_date: date | None = None,
) -> MagicMock:
    entry = MagicMock(spec=CabinetEntry)
    entry.id = uuid4()
    entry.user_id = _USER_ID
    entry.medication_registry_id = _REGISTRY_ID
    entry.package_count = package_count
    entry.partial_tablet_count = partial
    entry.expiry_date = _EXPIRY
    entry.is_important = is_important
    entry.is_used = is_used
    entry.dosage_times = dosage_times
    entry.dosage_period = dosage_period
    entry.dosage_amount = dosage_amount
    entry.dosage_start_date = dosage_start_date
    entry.dosage_end_date = dosage_end_date
    return entry


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

    async def test_fresh_insert_with_is_important_true(
        self, mock_session: AsyncMock, mock_crud
    ):
        variant = _make_variant(is_tablet_based=False, capacity=None)
        entry = _make_entry(package_count=1, is_important=True)
        mock_crud.get_registry_by_id = AsyncMock(return_value=variant)
        mock_crud.find_entry = AsyncMock(return_value=None)
        mock_crud.insert_entry = AsyncMock(return_value=entry)

        result = await add_entry(
            session=mock_session,
            user_id=_USER_ID,
            medication_registry_id=_REGISTRY_ID,
            package_count=1,
            partial_tablet_count=None,
            expiry_date=_EXPIRY,
            is_important=True,
        )

        assert result.merged is False
        assert result.entry.is_important is True
        call_kwargs = mock_crud.insert_entry.call_args.kwargs
        assert call_kwargs["is_important"] is True


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
        assert result.merge_summary is not None
        assert result.merge_summary.previous_package_count == 3

    @pytest.mark.parametrize(
        ("existing_important", "incoming_important", "expected_important"),
        [
            (False, True, True),  # non-important existing + important add → important
            (
                True,
                False,
                True,
            ),  # important existing + non-important add → stays important
            (True, True, True),  # both important → important
            (False, False, False),  # neither important → not important
        ],
        ids=["false+true", "true+false", "true+true", "false+false"],
    )
    async def test_merge_or_semantics_for_is_important(
        self,
        mock_session: AsyncMock,
        mock_crud,
        existing_important: bool,
        incoming_important: bool,
        expected_important: bool,
    ):
        variant = _make_variant(is_tablet_based=False, capacity=None)
        existing = _make_entry(package_count=1, is_important=existing_important)
        updated = _make_entry(package_count=2, is_important=expected_important)
        mock_crud.get_registry_by_id = AsyncMock(return_value=variant)
        mock_crud.find_entry = AsyncMock(return_value=existing)
        mock_crud.update_entry_counts = AsyncMock(return_value=updated)

        result = await add_entry(
            session=mock_session,
            user_id=_USER_ID,
            medication_registry_id=_REGISTRY_ID,
            package_count=1,
            partial_tablet_count=None,
            expiry_date=_EXPIRY,
            is_important=incoming_important,
        )

        assert result.merged is True
        assert result.entry.is_important is expected_important
        call_kwargs = mock_crud.update_entry_counts.call_args.kwargs
        assert call_kwargs["is_important"] is expected_important


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
# is_below_minimum
# ---------------------------------------------------------------------------


class TestIsBelowMinimum:
    @pytest.mark.parametrize(
        ("is_important_flag", "package_count", "min_package_count", "expected"),
        [
            (True, 0, 1, True),  # important, strictly below minimum
            (True, 1, 2, True),  # important, one below minimum of 2
            (True, 1, 1, False),  # important, exactly at minimum (no signal)
            (True, 2, 1, False),  # important, above minimum
            (False, 0, 1, False),  # not important, no signal regardless of count
            (False, 0, 5, False),  # not important, deeply below — still no signal
        ],
    )
    def test_is_below_minimum(
        self,
        is_important_flag: bool,
        package_count: int,
        min_package_count: int,
        expected: bool,
    ):
        assert (
            is_below_minimum(
                is_important=is_important_flag,
                package_count=package_count,
                min_package_count=min_package_count,
            )
            == expected
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
    async def test_returns_cabinet_page_out_with_status(
        self, mock_session: AsyncMock, mock_list_crud
    ):
        today = date.today()
        future = today + timedelta(days=60)
        entry = _make_real_entry(
            package_count=2, partial_tablet_count=5, expiry_date=future
        )
        variant = _make_variant(is_tablet_based=True, capacity=Decimal(20))
        mock_list_crud.list_entries = AsyncMock(return_value=([(entry, variant)], 1))

        result = await list_entries(
            session=mock_session,
            user_id=_USER_ID,
            expiry_threshold_days=30,
        )

        assert isinstance(result, CabinetPageOut)
        assert result.total == 1
        assert result.page == 1
        assert result.page_size == 20
        assert len(result.items) == 1
        assert result.items[0].status == Status.VALID
        assert result.items[0].total_tablets == 25  # (2-1)*20 + 5
        assert result.items[0].name == variant.name
        assert (
            result.items[0].route_of_administration == variant.route_of_administration
        )
        assert result.items[0].active_ingredient == variant.active_ingredient
        assert result.items[0].leaflet_url == variant.leaflet_url
        assert result.items[0].specification_url == variant.specification_url
        assert result.items[0].is_important is False
        assert result.items[0].below_minimum is False

    async def test_expired_entry_returns_expired_status(
        self, mock_session: AsyncMock, mock_list_crud
    ):
        past = date.today() - timedelta(days=1)
        entry = _make_real_entry(expiry_date=past)
        variant = _make_variant(is_tablet_based=False)
        mock_list_crud.list_entries = AsyncMock(return_value=([(entry, variant)], 1))

        result = await list_entries(
            session=mock_session, user_id=_USER_ID, expiry_threshold_days=30
        )

        assert result.items[0].status == Status.EXPIRED

    async def test_expiring_entry_returns_expiring_status(
        self, mock_session: AsyncMock, mock_list_crud
    ):
        soon = date.today() + timedelta(days=10)
        entry = _make_real_entry(expiry_date=soon)
        variant = _make_variant(is_tablet_based=False)
        mock_list_crud.list_entries = AsyncMock(return_value=([(entry, variant)], 1))

        result = await list_entries(
            session=mock_session, user_id=_USER_ID, expiry_threshold_days=30
        )

        assert result.items[0].status == Status.EXPIRING

    async def test_non_tablet_variant_has_none_total_tablets(
        self, mock_session: AsyncMock, mock_list_crud
    ):
        entry = _make_real_entry(package_count=3)
        variant = _make_variant(is_tablet_based=False)
        mock_list_crud.list_entries = AsyncMock(return_value=([(entry, variant)], 1))

        result = await list_entries(
            session=mock_session, user_id=_USER_ID, expiry_threshold_days=30
        )

        assert result.items[0].total_tablets is None
        assert result.items[0].package_count == 3

    async def test_empty_cabinet_returns_empty_page(
        self, mock_session: AsyncMock, mock_list_crud
    ):
        mock_list_crud.list_entries = AsyncMock(return_value=([], 0))

        result = await list_entries(
            session=mock_session, user_id=_USER_ID, expiry_threshold_days=30
        )

        assert isinstance(result, CabinetPageOut)
        assert result.items == []
        assert result.total == 0

    async def test_pagination_params_passed_to_crud(
        self, mock_session: AsyncMock, mock_list_crud
    ):
        mock_list_crud.list_entries = AsyncMock(return_value=([], 0))

        await list_entries(
            session=mock_session,
            user_id=_USER_ID,
            expiry_threshold_days=30,
            page=2,
            page_size=50,
            order="desc",
        )

        call_kwargs = mock_list_crud.list_entries.call_args.kwargs
        assert call_kwargs["limit"] == 50
        assert call_kwargs["offset"] == 50  # (page-1)*page_size = 1*50
        assert call_kwargs["order"] == "desc"

    async def test_search_q_converted_to_tsquery_for_crud(
        self, mock_session: AsyncMock, mock_list_crud
    ):
        mock_list_crud.list_entries = AsyncMock(return_value=([], 0))

        await list_entries(
            session=mock_session,
            user_id=_USER_ID,
            expiry_threshold_days=30,
            status="expiring",
            search="apap",
        )

        call_kwargs = mock_list_crud.list_entries.call_args.kwargs
        assert call_kwargs["status"] == "expiring"
        assert call_kwargs["tsquery"] == "apap:*"

    async def test_short_q_passes_none_tsquery_to_crud(
        self, mock_session: AsyncMock, mock_list_crud
    ):
        mock_list_crud.list_entries = AsyncMock(return_value=([], 0))

        await list_entries(
            session=mock_session,
            user_id=_USER_ID,
            expiry_threshold_days=30,
            search="a",
        )

        call_kwargs = mock_list_crud.list_entries.call_args.kwargs
        assert call_kwargs["tsquery"] is None

    @pytest.mark.parametrize(
        "capacity",
        [None, Decimal(0), Decimal(-5)],
        ids=["none", "zero", "negative"],
    )
    async def test_tablet_variant_with_invalid_capacity_yields_none_total_and_warns(
        self,
        mock_session: AsyncMock,
        mock_list_crud,
        mocker: MockerFixture,
        capacity: Decimal | None,
    ):
        spy_logger = mocker.patch("app.api.v1.cabinet.service.logger", autospec=True)
        entry = _make_real_entry(package_count=3)
        variant = _make_variant(is_tablet_based=True, capacity=capacity)
        mock_list_crud.list_entries = AsyncMock(return_value=([(entry, variant)], 1))

        result = await list_entries(
            session=mock_session,
            user_id=_USER_ID,
            expiry_threshold_days=30,
        )

        assert result.items[0].total_tablets is None
        spy_logger.warning.assert_called_once()

    async def test_important_entry_below_minimum_sets_below_minimum_true(
        self, mock_session: AsyncMock, mock_list_crud
    ):
        entry = CabinetEntry(
            id=_ENTRY_ID,
            user_id=_USER_ID,
            medication_registry_id=_REGISTRY_ID,
            package_count=1,
            partial_tablet_count=None,
            expiry_date=date.today() + timedelta(days=60),
            is_important=True,
        )
        variant = _make_variant(is_tablet_based=False)
        mock_list_crud.list_entries = AsyncMock(return_value=([(entry, variant)], 1))

        result = await list_entries(
            session=mock_session,
            user_id=_USER_ID,
            expiry_threshold_days=30,
            min_package_count=2,
        )

        assert result.items[0].is_important is True
        assert result.items[0].below_minimum is True

    async def test_important_entry_at_minimum_does_not_set_below_minimum(
        self, mock_session: AsyncMock, mock_list_crud
    ):
        entry = CabinetEntry(
            id=_ENTRY_ID,
            user_id=_USER_ID,
            medication_registry_id=_REGISTRY_ID,
            package_count=2,
            partial_tablet_count=None,
            expiry_date=date.today() + timedelta(days=60),
            is_important=True,
        )
        variant = _make_variant(is_tablet_based=False)
        mock_list_crud.list_entries = AsyncMock(return_value=([(entry, variant)], 1))

        result = await list_entries(
            session=mock_session,
            user_id=_USER_ID,
            expiry_threshold_days=30,
            min_package_count=2,
        )

        assert result.items[0].is_important is True
        assert result.items[0].below_minimum is False


# ---------------------------------------------------------------------------
# validate_usage
# ---------------------------------------------------------------------------

_TODAY = date(2026, 6, 25)


class TestValidateUsageNotUsed:
    def test_is_used_false_all_none_returns_cleared_resolved_usage(self):
        result = validate_usage(
            is_tablet_based=True,
            is_used=False,
            dosage_times=None,
            dosage_period=None,
            dosage_amount=None,
            dosage_start_date=None,
            dosage_end_date=None,
            today=_TODAY,
        )
        assert result.is_used is False
        assert result.dosage_times is None
        assert result.dosage_period is None
        assert result.dosage_amount is None
        assert result.dosage_start_date is None
        assert result.dosage_end_date is None

    @pytest.mark.parametrize(
        "extra_kwargs",
        [
            {"dosage_times": 2},
            {"dosage_period": DosagePeriod.day},
            {"dosage_amount": 1},
            {"dosage_start_date": _TODAY},
            {"dosage_end_date": _TODAY},
        ],
        ids=["times", "period", "amount", "start", "end"],
    )
    def test_is_used_false_with_any_field_raises(self, extra_kwargs):
        with pytest.raises(InvalidDosageError):
            validate_usage(
                is_tablet_based=True,
                is_used=False,
                dosage_times=extra_kwargs.get("dosage_times"),
                dosage_period=extra_kwargs.get("dosage_period"),
                dosage_amount=extra_kwargs.get("dosage_amount"),
                dosage_start_date=extra_kwargs.get("dosage_start_date"),
                dosage_end_date=extra_kwargs.get("dosage_end_date"),
                today=_TODAY,
            )


class TestValidateUsageTablet:
    def test_valid_tablet_usage_returns_resolved_usage(self):
        result = validate_usage(
            is_tablet_based=True,
            is_used=True,
            dosage_times=3,
            dosage_period=DosagePeriod.day,
            dosage_amount=2,
            dosage_start_date=None,
            dosage_end_date=None,
            today=_TODAY,
        )
        assert result.is_used is True
        assert result.dosage_times == 3
        assert result.dosage_period == DosagePeriod.day
        assert result.dosage_amount == 2
        assert result.dosage_start_date == _TODAY  # defaulted to today
        assert result.dosage_end_date is None

    def test_explicit_start_date_is_preserved(self):
        start = date(2026, 7, 1)
        result = validate_usage(
            is_tablet_based=True,
            is_used=True,
            dosage_times=1,
            dosage_period=DosagePeriod.week,
            dosage_amount=1,
            dosage_start_date=start,
            dosage_end_date=None,
            today=_TODAY,
        )
        assert result.dosage_start_date == start

    def test_end_date_after_start_is_accepted(self):
        result = validate_usage(
            is_tablet_based=True,
            is_used=True,
            dosage_times=2,
            dosage_period=DosagePeriod.day,
            dosage_amount=1,
            dosage_start_date=_TODAY,
            dosage_end_date=_TODAY + timedelta(days=30),
            today=_TODAY,
        )
        assert result.dosage_end_date == _TODAY + timedelta(days=30)

    @pytest.mark.parametrize(
        ("dosage_times", "dosage_period", "dosage_amount"),
        [
            (None, DosagePeriod.day, 1),
            (2, None, 1),
            (2, DosagePeriod.day, None),
        ],
        ids=["missing_times", "missing_period", "missing_amount"],
    )
    def test_tablet_missing_dosage_field_raises(
        self, dosage_times, dosage_period, dosage_amount
    ):
        with pytest.raises(InvalidDosageError):
            validate_usage(
                is_tablet_based=True,
                is_used=True,
                dosage_times=dosage_times,
                dosage_period=dosage_period,
                dosage_amount=dosage_amount,
                dosage_start_date=None,
                dosage_end_date=None,
                today=_TODAY,
            )

    def test_tablet_end_before_start_raises(self):
        with pytest.raises(InvalidDosageError):
            validate_usage(
                is_tablet_based=True,
                is_used=True,
                dosage_times=2,
                dosage_period=DosagePeriod.day,
                dosage_amount=1,
                dosage_start_date=_TODAY,
                dosage_end_date=_TODAY - timedelta(days=1),
                today=_TODAY,
            )


class TestValidateUsageNonTablet:
    def test_non_tablet_with_dates_only_accepted(self):
        result = validate_usage(
            is_tablet_based=False,
            is_used=True,
            dosage_times=None,
            dosage_period=None,
            dosage_amount=None,
            dosage_start_date=_TODAY,
            dosage_end_date=_TODAY + timedelta(days=10),
            today=_TODAY,
        )
        assert result.is_used is True
        assert result.dosage_times is None
        assert result.dosage_period is None
        assert result.dosage_amount is None
        assert result.dosage_start_date == _TODAY
        assert result.dosage_end_date == _TODAY + timedelta(days=10)

    @pytest.mark.parametrize(
        "extra_kwargs",
        [
            {"dosage_times": 2},
            {"dosage_period": DosagePeriod.day},
            {"dosage_amount": 1},
        ],
        ids=["times", "period", "amount"],
    )
    def test_non_tablet_with_dosage_field_raises(self, extra_kwargs):
        with pytest.raises(InvalidDosageError):
            validate_usage(
                is_tablet_based=False,
                is_used=True,
                dosage_times=extra_kwargs.get("dosage_times"),
                dosage_period=extra_kwargs.get("dosage_period"),
                dosage_amount=extra_kwargs.get("dosage_amount"),
                dosage_start_date=None,
                dosage_end_date=None,
                today=_TODAY,
            )

    def test_non_tablet_end_before_start_raises(self):
        with pytest.raises(InvalidDosageError):
            validate_usage(
                is_tablet_based=False,
                is_used=True,
                dosage_times=None,
                dosage_period=None,
                dosage_amount=None,
                dosage_start_date=_TODAY,
                dosage_end_date=_TODAY - timedelta(days=1),
                today=_TODAY,
            )


# ---------------------------------------------------------------------------
# add_entry with usage
# ---------------------------------------------------------------------------


class TestAddEntryWithUsage:
    async def test_usage_passed_to_insert_entry(
        self, mock_session: AsyncMock, mock_crud
    ):
        variant = _make_variant()
        entry = _make_entry(
            package_count=1,
            is_used=True,
            dosage_times=3,
            dosage_period="day",
            dosage_amount=2,
            dosage_start_date=_TODAY,
        )
        mock_crud.get_registry_by_id = AsyncMock(return_value=variant)
        mock_crud.find_entry = AsyncMock(return_value=None)
        mock_crud.insert_entry = AsyncMock(return_value=entry)

        result = await add_entry(
            session=mock_session,
            user_id=_USER_ID,
            medication_registry_id=_REGISTRY_ID,
            package_count=1,
            partial_tablet_count=None,
            expiry_date=_EXPIRY,
            usage=UsageFields(
                is_used=True,
                dosage_times=3,
                dosage_period=DosagePeriod.day,
                dosage_amount=2,
            ),
        )

        assert result.merged is False
        assert result.entry.is_used is True
        assert result.entry.dosage_times == 3
        assert result.entry.dosage_amount == 2
        call_kwargs = mock_crud.insert_entry.call_args.kwargs
        assert call_kwargs["resolved_usage"] is not None
        assert call_kwargs["resolved_usage"].is_used is True

    async def test_restock_without_usage_preserves_existing_schedule(
        self, mock_session: AsyncMock, mock_crud
    ):
        variant = _make_variant()
        existing = _make_entry(
            package_count=1,
            is_used=True,
            dosage_times=2,
            dosage_period="day",
            dosage_amount=1,
            dosage_start_date=_TODAY,
        )
        updated = _make_entry(
            package_count=2,
            is_used=True,
            dosage_times=2,
            dosage_period="day",
            dosage_amount=1,
            dosage_start_date=_TODAY,
        )
        mock_crud.get_registry_by_id = AsyncMock(return_value=variant)
        mock_crud.find_entry = AsyncMock(return_value=existing)
        mock_crud.update_entry_counts = AsyncMock(return_value=updated)

        result = await add_entry(
            session=mock_session,
            user_id=_USER_ID,
            medication_registry_id=_REGISTRY_ID,
            package_count=1,
            partial_tablet_count=None,
            expiry_date=_EXPIRY,
            usage=None,  # restock — no usage block
        )

        assert result.merged is True
        # update_entry_usage should NOT be called (no usage block provided)
        mock_crud.update_entry_usage.assert_not_called()

    async def test_merge_with_usage_persists_usage_atomically(
        self, mock_session: AsyncMock, mock_crud
    ):
        variant = _make_variant()
        existing = _make_entry(package_count=1)
        updated = _make_entry(
            package_count=2,
            is_used=True,
            dosage_times=1,
            dosage_period="day",
            dosage_amount=1,
            dosage_start_date=_TODAY,
        )
        mock_crud.get_registry_by_id = AsyncMock(return_value=variant)
        mock_crud.find_entry = AsyncMock(return_value=existing)
        mock_crud.update_entry_counts = AsyncMock(return_value=updated)

        await add_entry(
            session=mock_session,
            user_id=_USER_ID,
            medication_registry_id=_REGISTRY_ID,
            package_count=1,
            partial_tablet_count=None,
            expiry_date=_EXPIRY,
            usage=UsageFields(
                is_used=True,
                dosage_times=1,
                dosage_period=DosagePeriod.day,
                dosage_amount=1,
            ),
        )

        # Usage is folded into the single update_entry_counts transaction, not a
        # separate update_entry_usage commit, so the merge stays atomic (impl review F1).
        mock_crud.update_entry_usage.assert_not_called()
        mock_crud.update_entry_counts.assert_called_once()
        call_kwargs = mock_crud.update_entry_counts.call_args.kwargs
        assert call_kwargs["resolved_usage"].is_used is True

    async def test_invalid_dosage_raises_invalid_dosage_error(
        self, mock_session: AsyncMock, mock_crud
    ):
        variant = _make_variant()
        mock_crud.get_registry_by_id = AsyncMock(return_value=variant)

        with pytest.raises(InvalidDosageError):
            await add_entry(
                session=mock_session,
                user_id=_USER_ID,
                medication_registry_id=_REGISTRY_ID,
                package_count=1,
                partial_tablet_count=None,
                expiry_date=_EXPIRY,
                usage=UsageFields(
                    is_used=True,
                    # missing dosage_times / dosage_period / dosage_amount for tablet
                ),
            )


# ---------------------------------------------------------------------------
# daily_consumption_rate
# ---------------------------------------------------------------------------


class TestDailyConsumptionRate:
    @pytest.mark.parametrize(
        ("dosage_times", "dosage_amount", "dosage_period", "expected"),
        [
            (1, 1, DosagePeriod.day, 1.0),
            (3, 2, DosagePeriod.day, 6.0),
            (2, 3, DosagePeriod.week, 6 / 7),
            (1, 7, DosagePeriod.week, 1.0),
        ],
    )
    def test_daily_consumption_rate(
        self, dosage_times, dosage_amount, dosage_period, expected
    ):
        result = daily_consumption_rate(
            dosage_times=dosage_times,
            dosage_amount=dosage_amount,
            dosage_period=dosage_period,
        )
        assert abs(result - expected) < 1e-9


# ---------------------------------------------------------------------------
# days_of_supply_from_rate
# ---------------------------------------------------------------------------


class TestDaysOfSupplyFromRate:
    @pytest.mark.parametrize(
        ("total_tablets_count", "daily_rate", "expected"),
        [
            (10, 3.0, 3),  # floor: 10/3 = 3.33 → 3
            (20, 2.0, 10),
            (7, 1.0, 7),
            (0, 2.0, 0),
            (10, 0.0, None),  # zero rate guard
            (10, -1.0, None),  # negative rate guard
        ],
    )
    def test_days_of_supply_from_rate(self, total_tablets_count, daily_rate, expected):
        result = days_of_supply_from_rate(
            total_tablets_count=total_tablets_count,
            daily_rate=daily_rate,
        )
        assert result == expected


# ---------------------------------------------------------------------------
# compute_usage_view
# ---------------------------------------------------------------------------


def _make_used_entry(
    package_count: int = 2,
    partial_tablet_count: int | None = None,
    is_used: bool = True,
    dosage_times: int | None = 3,
    dosage_amount: int | None = 2,
    dosage_period: str | None = DosagePeriod.day,
    dosage_start_date: date | None = None,
    dosage_end_date: date | None = None,
) -> CabinetEntry:
    entry = CabinetEntry(
        id=_ENTRY_ID,
        user_id=_USER_ID,
        medication_registry_id=_REGISTRY_ID,
        package_count=package_count,
        partial_tablet_count=partial_tablet_count,
        expiry_date=_EXPIRY,
    )
    entry.is_used = is_used
    entry.dosage_times = dosage_times
    entry.dosage_amount = dosage_amount
    entry.dosage_period = dosage_period
    entry.dosage_start_date = dosage_start_date
    entry.dosage_end_date = dosage_end_date
    return entry


_TODAY = date(2026, 6, 26)


class TestComputeUsageView:
    def test_not_used_returns_all_none(self):
        entry = _make_used_entry(
            is_used=False, dosage_times=None, dosage_amount=None, dosage_period=None
        )
        result = compute_usage_view(entry=entry, tablets_per_package=20, today=_TODAY)
        assert result == UsageView(
            days_of_supply=None, days_until_end=None, is_sufficient=None
        )

    def test_no_tablets_per_package_returns_all_none(self):
        entry = _make_used_entry()
        result = compute_usage_view(entry=entry, tablets_per_package=None, today=_TODAY)
        assert result == UsageView(
            days_of_supply=None, days_until_end=None, is_sufficient=None
        )

    def test_non_tablet_used_entry_returns_all_none(self):
        entry = _make_used_entry(
            dosage_times=None, dosage_amount=None, dosage_period=None
        )
        result = compute_usage_view(entry=entry, tablets_per_package=None, today=_TODAY)
        assert result == UsageView(
            days_of_supply=None, days_until_end=None, is_sufficient=None
        )

    def test_per_day_no_end_date(self):
        # 2 packages × 20 tpp = 40 tablets; rate = 3×2/day = 6; supply = floor(40/6) = 6
        entry = _make_used_entry(
            package_count=2,
            dosage_times=3,
            dosage_amount=2,
            dosage_period=DosagePeriod.day,
        )
        result = compute_usage_view(entry=entry, tablets_per_package=20, today=_TODAY)
        assert result.days_of_supply == 6
        assert result.days_until_end is None
        assert result.is_sufficient is None

    def test_per_week_rate(self):
        # 1 package × 14 tpp = 14 tablets; rate = 2×1/week = 2/7; supply = floor(14/(2/7)) = floor(49) = 49
        entry = _make_used_entry(
            package_count=1,
            dosage_times=2,
            dosage_amount=1,
            dosage_period=DosagePeriod.week,
        )
        result = compute_usage_view(entry=entry, tablets_per_package=14, today=_TODAY)
        assert result.days_of_supply == 49
        assert result.days_until_end is None

    def test_partial_package_included(self):
        # 2 packages, 5 partial → (2-1)*20+5 = 25 tablets; rate=3*2/day=6; supply=floor(25/6)=4
        entry = _make_used_entry(
            package_count=2,
            partial_tablet_count=5,
            dosage_times=3,
            dosage_amount=2,
            dosage_period=DosagePeriod.day,
        )
        result = compute_usage_view(entry=entry, tablets_per_package=20, today=_TODAY)
        assert result.days_of_supply == 4

    def test_floor_boundary(self):
        # 10 tablets / 3 per day = 3.33 → floor = 3
        entry = _make_used_entry(
            package_count=1,
            dosage_times=3,
            dosage_amount=1,
            dosage_period=DosagePeriod.day,
        )
        result = compute_usage_view(entry=entry, tablets_per_package=10, today=_TODAY)
        assert result.days_of_supply == 3

    def test_sufficient_with_future_end_date(self):
        # 40 tablets / 2 per day = 20 days supply; end in 10 days → sufficient
        end = _TODAY + timedelta(days=10)
        entry = _make_used_entry(
            package_count=2,
            dosage_times=2,
            dosage_amount=1,
            dosage_period=DosagePeriod.day,
            dosage_end_date=end,
        )
        result = compute_usage_view(entry=entry, tablets_per_package=20, today=_TODAY)
        assert result.days_of_supply == 20
        assert result.days_until_end == 10
        assert result.is_sufficient is True

    def test_short_with_future_end_date(self):
        # 6 tablets / 2 per day = 3 days supply; end in 10 days → short
        end = _TODAY + timedelta(days=10)
        entry = _make_used_entry(
            package_count=1,
            dosage_times=2,
            dosage_amount=1,
            dosage_period=DosagePeriod.day,
            dosage_end_date=end,
        )
        result = compute_usage_view(entry=entry, tablets_per_package=6, today=_TODAY)
        assert result.days_of_supply == 3
        assert result.days_until_end == 10
        assert result.is_sufficient is False

    def test_end_date_in_past(self):
        past = _TODAY - timedelta(days=3)
        entry = _make_used_entry(
            package_count=2,
            dosage_times=1,
            dosage_amount=1,
            dosage_period=DosagePeriod.day,
            dosage_end_date=past,
        )
        result = compute_usage_view(entry=entry, tablets_per_package=20, today=_TODAY)
        assert result.days_until_end == -3
        # Window already closed (days_until_end <= 0): no sufficiency verdict.
        assert result.is_sufficient is None


# ---------------------------------------------------------------------------
# set_entry_usage
# ---------------------------------------------------------------------------


class TestSetEntryUsage:
    async def test_sets_usage_on_existing_entry(
        self, mock_session: AsyncMock, mock_crud
    ):
        variant = _make_variant()
        entry = _make_entry(package_count=2)
        updated = _make_entry(
            package_count=2,
            is_used=True,
            dosage_times=3,
            dosage_period="day",
            dosage_amount=2,
            dosage_start_date=_TODAY,
        )
        mock_crud.find_entry_by_id = AsyncMock(return_value=entry)
        mock_crud.get_registry_by_id = AsyncMock(return_value=variant)
        mock_crud.update_entry_usage = AsyncMock(return_value=updated)

        result = await set_entry_usage(
            session=mock_session,
            user_id=_USER_ID,
            entry_id=_ENTRY_ID,
            usage=UsageFields(
                is_used=True,
                dosage_times=3,
                dosage_period=DosagePeriod.day,
                dosage_amount=2,
            ),
            expiry_threshold_days=30,
        )

        assert result.is_used is True
        assert result.dosage_times == 3
        assert result.dosage_amount == 2
        mock_crud.update_entry_usage.assert_called_once()

    async def test_unassign_clears_dosage_columns(
        self, mock_session: AsyncMock, mock_crud
    ):
        variant = _make_variant()
        entry = _make_entry(
            package_count=1,
            is_used=True,
            dosage_times=2,
            dosage_period="day",
            dosage_amount=1,
            dosage_start_date=_TODAY,
        )
        cleared = _make_entry(package_count=1, is_used=False)
        mock_crud.find_entry_by_id = AsyncMock(return_value=entry)
        mock_crud.get_registry_by_id = AsyncMock(return_value=variant)
        mock_crud.update_entry_usage = AsyncMock(return_value=cleared)

        result = await set_entry_usage(
            session=mock_session,
            user_id=_USER_ID,
            entry_id=_ENTRY_ID,
            usage=UsageFields(is_used=False),
            expiry_threshold_days=30,
        )

        assert result.is_used is False
        call_kwargs = mock_crud.update_entry_usage.call_args.kwargs
        assert call_kwargs["resolved_usage"].is_used is False
        assert call_kwargs["resolved_usage"].dosage_times is None
        assert call_kwargs["resolved_usage"].dosage_amount is None

    async def test_entry_not_found_raises_entry_not_found_error(
        self, mock_session: AsyncMock, mock_crud
    ):
        mock_crud.find_entry_by_id = AsyncMock(return_value=None)

        with pytest.raises(EntryNotFoundError):
            await set_entry_usage(
                session=mock_session,
                user_id=_USER_ID,
                entry_id=_ENTRY_ID,
                usage=UsageFields(is_used=False),
                expiry_threshold_days=30,
            )

    async def test_invalid_dosage_raises_invalid_dosage_error(
        self, mock_session: AsyncMock, mock_crud
    ):
        variant = _make_variant()
        entry = _make_entry()
        mock_crud.find_entry_by_id = AsyncMock(return_value=entry)
        mock_crud.get_registry_by_id = AsyncMock(return_value=variant)

        with pytest.raises(InvalidDosageError):
            await set_entry_usage(
                session=mock_session,
                user_id=_USER_ID,
                entry_id=_ENTRY_ID,
                usage=UsageFields(
                    is_used=True,
                    # missing dosage_times/period/amount for tablet variant
                ),
                expiry_threshold_days=30,
            )


class TestDeleteEntry:
    async def test_deletes_owned_entry(self, mock_session: AsyncMock, mock_crud):
        entry = _make_entry()
        mock_crud.find_entry_by_id = AsyncMock(return_value=entry)
        mock_crud.delete_entry = AsyncMock(return_value=None)

        await delete_entry(session=mock_session, user_id=_USER_ID, entry_id=_ENTRY_ID)

        mock_crud.delete_entry.assert_called_once_with(
            session=mock_session, entry=entry
        )

    async def test_entry_not_found_raises_entry_not_found_error(
        self, mock_session: AsyncMock, mock_crud
    ):
        mock_crud.find_entry_by_id = AsyncMock(return_value=None)

        with pytest.raises(EntryNotFoundError):
            await delete_entry(
                session=mock_session, user_id=_USER_ID, entry_id=_ENTRY_ID
            )
