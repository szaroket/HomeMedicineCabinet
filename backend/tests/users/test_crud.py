"""Unit tests for users CRUD layer."""

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from sqlalchemy import Result
from sqlalchemy.exc import SQLAlchemyError

from app.api.v1.users.crud import (
    delete_user_rows,
    get_user_preferences,
    insert_preferences,
    update_preferences,
)
from app.api.v1.users.models import UserPreferences
from app.utilities.const import (
    DEFAULT_CLOSE_TO_FINISH_THRESHOLD_DAYS,
    DEFAULT_EXPIRY_THRESHOLD_DAYS,
)
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

        with pytest.raises(UserDatabaseError) as exc_info:
            await get_user_preferences(mock_session, _USER_ID)

        assert (
            exc_info.value.message == "A database error occurred in the users domain."
        )

    async def test_db_error_is_chained(self, mock_session: AsyncMock):
        original = SQLAlchemyError("timeout")
        mock_session.execute.side_effect = original

        with pytest.raises(UserDatabaseError) as exc_info:
            await get_user_preferences(mock_session, _USER_ID)

        assert exc_info.value.__cause__ is original


def _mock_persist(side_effect=None):
    cm = MagicMock()
    cm.__aenter__ = AsyncMock(return_value=None)
    cm.__aexit__ = AsyncMock(return_value=False, side_effect=side_effect)
    return cm


class TestUpdatePreferences:
    def _make_prefs(self) -> MagicMock:
        prefs = MagicMock(spec=UserPreferences)
        prefs.user_id = _USER_ID
        prefs.expiry_threshold_days = 30
        prefs.close_to_finish_threshold_days = 7
        prefs.min_package_count = 1
        return prefs

    async def test_sets_all_fields_and_returns_prefs(self, mock_session: AsyncMock):
        prefs = self._make_prefs()
        with patch("app.api.v1.users.crud.persist", return_value=_mock_persist()):
            result = await update_preferences(
                session=mock_session,
                prefs=prefs,
                expiry_threshold_days=14,
                close_to_finish_threshold_days=3,
                min_package_count=4,
            )

        assert result is prefs
        assert prefs.expiry_threshold_days == 14
        assert prefs.close_to_finish_threshold_days == 3
        assert prefs.min_package_count == 4

    async def test_db_error_raises_user_database_error(self, mock_session: AsyncMock):
        prefs = self._make_prefs()
        with patch(
            "app.api.v1.users.crud.persist",
            return_value=_mock_persist(side_effect=SQLAlchemyError("disk full")),
        ):
            with pytest.raises(UserDatabaseError) as exc_info:
                await update_preferences(
                    session=mock_session,
                    prefs=prefs,
                    expiry_threshold_days=14,
                    close_to_finish_threshold_days=3,
                    min_package_count=4,
                )

        assert (
            exc_info.value.message == "A database error occurred in the users domain."
        )

    async def test_db_error_is_chained(self, mock_session: AsyncMock):
        prefs = self._make_prefs()
        original = SQLAlchemyError("disk full")
        with patch(
            "app.api.v1.users.crud.persist",
            return_value=_mock_persist(side_effect=original),
        ):
            with pytest.raises(UserDatabaseError) as exc_info:
                await update_preferences(
                    session=mock_session,
                    prefs=prefs,
                    expiry_threshold_days=14,
                    close_to_finish_threshold_days=3,
                    min_package_count=4,
                )

        assert exc_info.value.__cause__ is original


class TestInsertPreferences:
    def _make_new_prefs(self) -> UserPreferences:
        return UserPreferences(
            user_id=_USER_ID,
            expiry_threshold_days=DEFAULT_EXPIRY_THRESHOLD_DAYS,
            close_to_finish_threshold_days=DEFAULT_CLOSE_TO_FINISH_THRESHOLD_DAYS,
            min_package_count=3,
        )

    async def test_returns_inserted_prefs(self, mock_session: AsyncMock):
        prefs = self._make_new_prefs()
        with patch("app.api.v1.users.crud.persist", return_value=_mock_persist()):
            result = await insert_preferences(session=mock_session, prefs=prefs)

        assert result is prefs

    async def test_db_error_raises_user_database_error(self, mock_session: AsyncMock):
        prefs = self._make_new_prefs()
        with patch(
            "app.api.v1.users.crud.persist",
            return_value=_mock_persist(side_effect=SQLAlchemyError("disk full")),
        ):
            with pytest.raises(UserDatabaseError) as exc_info:
                await insert_preferences(session=mock_session, prefs=prefs)

        assert (
            exc_info.value.message == "A database error occurred in the users domain."
        )

    async def test_db_error_is_chained(self, mock_session: AsyncMock):
        prefs = self._make_new_prefs()
        original = SQLAlchemyError("disk full")
        with patch(
            "app.api.v1.users.crud.persist",
            return_value=_mock_persist(side_effect=original),
        ):
            with pytest.raises(UserDatabaseError) as exc_info:
                await insert_preferences(session=mock_session, prefs=prefs)

        assert exc_info.value.__cause__ is original


class TestDeleteUserRows:
    async def test_success_issues_both_delete_statements(self, mock_session: AsyncMock):
        await delete_user_rows(mock_session, _USER_ID)

        assert mock_session.execute.call_count == 2
        mock_session.commit.assert_not_called()

    async def test_db_error_raises_user_database_error(self, mock_session: AsyncMock):
        mock_session.execute.side_effect = SQLAlchemyError("lock timeout")

        with pytest.raises(UserDatabaseError):
            await delete_user_rows(mock_session, _USER_ID)

    async def test_db_error_is_chained(self, mock_session: AsyncMock):
        original = SQLAlchemyError("lock timeout")
        mock_session.execute.side_effect = original

        with pytest.raises(UserDatabaseError) as exc_info:
            await delete_user_rows(mock_session, _USER_ID)

        assert exc_info.value.__cause__ is original
