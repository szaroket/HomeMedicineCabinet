"""Unit tests for cabinet CRUD layer (DB operations, no HTTP)."""

from datetime import date
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from sqlalchemy import Result
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from app.api.v1.cabinet.crud import (
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
