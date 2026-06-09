"""Unit tests for medicines CRUD layer (DB operations, no HTTP).

Uses the shared ``mock_session`` fixture from ``tests/conftest.py``.
"""

from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy import Result, Row
from sqlalchemy.exc import SQLAlchemyError

from app.api.v1.medicines.crud import search_products
from app.utilities.errors import MedicineSearchError

_FAKE_TSQUERY = "apap:* & forte:*"
_FAKE_LIMIT = 20


def _result_returning(rows: list) -> MagicMock:
    """Build a stand-in execute() Result whose .all() yields the given rows."""
    result = MagicMock(spec=Result)
    result.all.return_value = rows
    return result


class TestSearchProducts:
    @pytest.mark.asyncio
    async def test_success_returns_all_rows(self, mock_session: AsyncMock):
        rows = [MagicMock(spec=Row), MagicMock(spec=Row)]
        mock_session.execute.return_value = _result_returning(rows)

        result = await search_products(mock_session, _FAKE_TSQUERY, _FAKE_LIMIT)

        assert result == rows

    @pytest.mark.asyncio
    async def test_binds_tsquery_and_limit_as_parameters(self, mock_session: AsyncMock):
        mock_session.execute.return_value = _result_returning([])

        await search_products(mock_session, _FAKE_TSQUERY, _FAKE_LIMIT)

        mock_session.execute.assert_awaited_once()
        _, params = mock_session.execute.await_args.args
        assert params == {"tsquery": _FAKE_TSQUERY, "limit": _FAKE_LIMIT}

    @pytest.mark.asyncio
    async def test_db_error_raises_medicine_search_error(self, mock_session: AsyncMock):
        mock_session.execute.side_effect = SQLAlchemyError("connection lost")

        with pytest.raises(MedicineSearchError):
            await search_products(mock_session, _FAKE_TSQUERY, _FAKE_LIMIT)

    @pytest.mark.asyncio
    async def test_db_error_is_chained(self, mock_session: AsyncMock):
        original = SQLAlchemyError("connection lost")
        mock_session.execute.side_effect = original

        with pytest.raises(MedicineSearchError) as exc_info:
            await search_products(mock_session, _FAKE_TSQUERY, _FAKE_LIMIT)

        assert exc_info.value.__cause__ is original
