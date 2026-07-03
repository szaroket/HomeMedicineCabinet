"""Unit tests for cabinet CRUD layer (DB operations, no HTTP)."""

from datetime import date
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from sqlalchemy import Result
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from app.api.v1.cabinet.crud import (
    _build_base_query,
    delete_entry,
    find_entry,
    get_registry_by_id,
    insert_entry,
    update_entry_counts,
)
from app.api.v1.cabinet.models import CabinetEntry
from app.api.v1.medicines.models import MedicationRegistry
from app.utilities.errors import CabinetDatabaseError

_USER_ID = uuid4()
_REGISTRY_ID = uuid4()
_EXPIRY = date(2027, 1, 1)


def _scalar_result(value) -> MagicMock:
    result = MagicMock(spec=Result)
    result.scalar_one_or_none.return_value = value
    return result


class TestGetRegistryById:
    async def test_returns_row_when_found(self, mock_session: AsyncMock):
        registry = MagicMock(spec=MedicationRegistry)
        mock_session.execute.return_value = _scalar_result(registry)

        result = await get_registry_by_id(mock_session, _REGISTRY_ID)

        assert result is registry

    async def test_returns_none_when_not_found(self, mock_session: AsyncMock):
        mock_session.execute.return_value = _scalar_result(None)

        result = await get_registry_by_id(mock_session, _REGISTRY_ID)

        assert result is None

    async def test_db_error_raises_cabinet_database_error(
        self, mock_session: AsyncMock
    ):
        mock_session.execute.side_effect = SQLAlchemyError("timeout")

        with pytest.raises(CabinetDatabaseError):
            await get_registry_by_id(mock_session, _REGISTRY_ID)

    async def test_db_error_is_chained(self, mock_session: AsyncMock):
        original = SQLAlchemyError("timeout")
        mock_session.execute.side_effect = original

        with pytest.raises(CabinetDatabaseError) as exc_info:
            await get_registry_by_id(mock_session, _REGISTRY_ID)

        assert exc_info.value.__cause__ is original


class TestFindEntry:
    async def test_returns_entry_when_found(self, mock_session: AsyncMock):
        entry = MagicMock(spec=CabinetEntry)
        mock_session.execute.return_value = _scalar_result(entry)

        result = await find_entry(mock_session, _USER_ID, _REGISTRY_ID, _EXPIRY)

        assert result is entry

    async def test_returns_none_when_not_found(self, mock_session: AsyncMock):
        mock_session.execute.return_value = _scalar_result(None)

        result = await find_entry(mock_session, _USER_ID, _REGISTRY_ID, _EXPIRY)

        assert result is None

    async def test_db_error_raises_cabinet_database_error(
        self, mock_session: AsyncMock
    ):
        mock_session.execute.side_effect = SQLAlchemyError("timeout")

        with pytest.raises(CabinetDatabaseError):
            await find_entry(mock_session, _USER_ID, _REGISTRY_ID, _EXPIRY)


class TestInsertEntry:
    async def test_success_returns_entry(self, mock_session: AsyncMock):
        with patch("app.api.v1.cabinet.crud.persist", autospec=True) as mock_persist_cm:
            mock_persist_cm.return_value.__aenter__ = AsyncMock(return_value=None)
            mock_persist_cm.return_value.__aexit__ = AsyncMock(return_value=False)

            result = await insert_entry(
                mock_session, _USER_ID, _REGISTRY_ID, 2, 5, _EXPIRY
            )

        assert isinstance(result, CabinetEntry)
        assert result.user_id == _USER_ID
        assert result.medication_registry_id == _REGISTRY_ID
        assert result.package_count == 2
        assert result.partial_tablet_count == 5
        assert result.expiry_date == _EXPIRY

    async def test_db_error_raises_cabinet_database_error(
        self, mock_session: AsyncMock
    ):
        with patch("app.api.v1.cabinet.crud.persist", autospec=True) as mock_persist_cm:
            mock_persist_cm.return_value.__aenter__ = AsyncMock(return_value=None)
            mock_persist_cm.return_value.__aexit__ = AsyncMock(
                side_effect=SQLAlchemyError("disk full")
            )

            with pytest.raises(CabinetDatabaseError):
                await insert_entry(
                    mock_session, _USER_ID, _REGISTRY_ID, 1, None, _EXPIRY
                )

    async def test_db_error_is_chained(self, mock_session: AsyncMock):
        original = SQLAlchemyError("disk full")
        with patch("app.api.v1.cabinet.crud.persist", autospec=True) as mock_persist_cm:
            mock_persist_cm.return_value.__aenter__ = AsyncMock(return_value=None)
            mock_persist_cm.return_value.__aexit__ = AsyncMock(side_effect=original)

            with pytest.raises(CabinetDatabaseError) as exc_info:
                await insert_entry(
                    mock_session, _USER_ID, _REGISTRY_ID, 1, None, _EXPIRY
                )

        assert exc_info.value.__cause__ is original

    async def test_integrity_error_propagates_untouched(self, mock_session: AsyncMock):
        # A duplicate-key IntegrityError must NOT be wrapped in
        # CabinetDatabaseError: it has to reach the service-layer race guard so
        # the concurrent-add merge (FR-010) can run.
        integrity_error = IntegrityError("unique", {}, Exception())
        with patch("app.api.v1.cabinet.crud.persist", autospec=True) as mock_persist_cm:
            mock_persist_cm.return_value.__aenter__ = AsyncMock(return_value=None)
            mock_persist_cm.return_value.__aexit__ = AsyncMock(
                side_effect=integrity_error
            )

            with pytest.raises(IntegrityError) as exc_info:
                await insert_entry(
                    mock_session, _USER_ID, _REGISTRY_ID, 1, None, _EXPIRY
                )

        assert exc_info.value is integrity_error


class TestBuildBaseQueryBelowMinimum:
    """Restrict to important entries under the minimum, no-op without a minimum.

    The below_minimum filter must no-op when the user has no resolved minimum.
    The discriminating clause is the ``package_count < :min`` comparison: it is
    rendered only when the filter is active. (``is_important IS true`` is shared
    with the category=important filter, so it is not a reliable discriminator.)
    """

    @pytest.mark.parametrize(
        ("below_minimum", "min_package_count", "expect_clause"),
        [
            (True, 2, True),  # active filter: important AND package_count < 2
            (True, None, False),  # None-guard no-op: user has no minimum resolved
            (False, 2, False),  # filter explicitly off
            (None, 2, False),  # filter unset
        ],
    )
    def test_package_count_clause_present_only_when_active(
        self,
        below_minimum: bool | None,
        min_package_count: int | None,
        expect_clause: bool,
    ):
        stmt = _build_base_query(
            user_id=_USER_ID,
            today=_EXPIRY,
            threshold=30,
            status=None,
            tsquery=None,
            below_minimum=below_minimum,
            min_package_count=min_package_count,
        )

        sql = str(stmt)

        assert ("package_count <" in sql) is expect_clause


class TestBuildBaseQuerySufficiency:
    """Pin the SQL sufficiency filter to the Python calc in cabinet.service.

    The set-based filter duplicates ``compute_usage_view`` / ``days_of_supply``
    arithmetic because SQL cannot call the per-row Python code (Risk #6). These
    tests pin the two paths together: the SQL must reproduce the same None-case
    guards so a row matches a filter exactly when the Python verdict is non-None.
    Change here together with ``cabinet.service`` if the calc ever changes.
    """

    def _sql(self, sufficiency: str | None) -> str:
        stmt = _build_base_query(
            user_id=_USER_ID,
            today=_EXPIRY,
            threshold=30,
            status=None,
            tsquery=None,
            sufficiency=sufficiency,
        )
        return str(stmt)

    @pytest.mark.parametrize("sufficiency", ["insufficient", "sufficient"])
    def test_closed_window_excluded(self, sufficiency: str):
        # Mirrors compute_usage_view's until_end > 0 gate: an entry whose window
        # is already closed (end date today or past) yields is_sufficient=None,
        # so it must match neither filter. Without this guard the SQL "sufficient"
        # filter returns rows that render no badge (finding F2).
        assert "dosage_end_date > " in self._sql(sufficiency)

    @pytest.mark.parametrize("sufficiency", ["insufficient", "sufficient"])
    def test_zero_rate_guarded(self, sufficiency: str):
        # Mirrors days_of_supply_from_rate returning None for daily_rate <= 0:
        # NULLIF(rate, 0) yields a NULL verdict (no match) instead of a DB
        # divide-by-zero, regardless of WHERE evaluation order (finding F4).
        assert "nullif(" in self._sql(sufficiency)

    @pytest.mark.parametrize("sufficiency", ["insufficient", "sufficient"])
    def test_used_tablet_entries_only(self, sufficiency: str):
        sql = self._sql(sufficiency)
        assert "is_used IS true" in sql
        assert "capacity IS NOT NULL" in sql

    def test_insufficient_projects_finish_before_end(self):
        # days_of_supply runs out before the window ends -> short.
        assert "AS INTEGER) < cabinet_entries.dosage_end_date" in self._sql(
            "insufficient"
        )

    def test_sufficient_projects_finish_at_or_after_end(self):
        # supply lasts to/through the window end -> sufficient.
        assert "AS INTEGER) >= cabinet_entries.dosage_end_date" in self._sql(
            "sufficient"
        )

    @pytest.mark.parametrize("sufficiency", [None, "all", ""])
    def test_no_sufficiency_clause_when_inactive(self, sufficiency: str | None):
        sql = self._sql(sufficiency)
        assert "nullif(" not in sql
        assert "dosage_end_date > " not in sql


class TestUpdateEntryCounts:
    def _make_entry(self) -> CabinetEntry:
        entry = CabinetEntry(
            id=uuid4(),
            user_id=_USER_ID,
            medication_registry_id=_REGISTRY_ID,
            package_count=1,
            expiry_date=_EXPIRY,
        )
        return entry

    async def test_success_updates_and_returns_entry(self, mock_session: AsyncMock):
        entry = self._make_entry()
        with patch("app.api.v1.cabinet.crud.persist", autospec=True) as mock_persist_cm:
            mock_persist_cm.return_value.__aenter__ = AsyncMock(return_value=None)
            mock_persist_cm.return_value.__aexit__ = AsyncMock(return_value=False)

            result = await update_entry_counts(mock_session, entry, 3, 7)

        assert result is entry
        assert entry.package_count == 3
        assert entry.partial_tablet_count == 7

    async def test_db_error_raises_cabinet_database_error(
        self, mock_session: AsyncMock
    ):
        entry = self._make_entry()
        with patch("app.api.v1.cabinet.crud.persist", autospec=True) as mock_persist_cm:
            mock_persist_cm.return_value.__aenter__ = AsyncMock(return_value=None)
            mock_persist_cm.return_value.__aexit__ = AsyncMock(
                side_effect=SQLAlchemyError("lock timeout")
            )

            with pytest.raises(CabinetDatabaseError):
                await update_entry_counts(mock_session, entry, 3, 7)


class TestDeleteEntry:
    def _make_entry(self) -> CabinetEntry:
        return CabinetEntry(
            id=uuid4(),
            user_id=_USER_ID,
            medication_registry_id=_REGISTRY_ID,
            package_count=1,
            expiry_date=_EXPIRY,
        )

    async def test_success_deletes_and_commits(self, mock_session: AsyncMock):
        entry = self._make_entry()

        await delete_entry(mock_session, entry)

        mock_session.delete.assert_called_once_with(entry)
        mock_session.commit.assert_called_once()

    async def test_db_error_raises_cabinet_database_error(
        self, mock_session: AsyncMock
    ):
        entry = self._make_entry()
        mock_session.delete.side_effect = SQLAlchemyError("lock timeout")

        with pytest.raises(CabinetDatabaseError):
            await delete_entry(mock_session, entry)
