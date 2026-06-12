"""Unit tests for users CRUD layer."""

from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from sqlalchemy import Result
from sqlalchemy.exc import SQLAlchemyError

from app.api.v1.users.crud import get_user_preferences
from app.api.v1.users.models import UserPreferences
from app.utilities.errors import UserDatabaseError

_USER_ID = uuid4()


def _scalar_result(value) -> MagicMock:
    result = MagicMock(spec=Result)
    result.scalar_one_or_none.return_value = value
    return result


class TestGetUserPreferences:
    async def test_returns_prefs_when_found(self, mock_session: AsyncMock):
        prefs = MagicMock(spec=UserPreferences)
        mock_session.execute.return_value = _scalar_result(prefs)

        result = await get_user_preferences(mock_session, _USER_ID)

        assert result is prefs

    async def test_returns_none_when_not_found(self, mock_session: AsyncMock):
        mock_session.execute.return_value = _scalar_result(None)

        result = await get_user_preferences(mock_session, _USER_ID)

        assert result is None

    async def test_db_error_raises_user_database_error(self, mock_session: AsyncMock):
        mock_session.execute.side_effect = SQLAlchemyError("timeout")

        with pytest.raises(UserDatabaseError):
            await get_user_preferences(mock_session, _USER_ID)

    async def test_db_error_is_chained(self, mock_session: AsyncMock):
        original = SQLAlchemyError("timeout")
        mock_session.execute.side_effect = original

        with pytest.raises(UserDatabaseError) as exc_info:
            await get_user_preferences(mock_session, _USER_ID)

        assert exc_info.value.__cause__ is original
