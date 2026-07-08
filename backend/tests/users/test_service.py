"""Unit tests for users service layer."""

from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

from pytest_mock import MockerFixture

from app.api.v1.users.models import UserPreferences
from app.api.v1.users.schemas import UserPreferencesOut
from app.api.v1.users.service import (
    delete_user_rows,
    get_effective_preferences,
    update_preferences,
)
from app.utilities.const import (
    DEFAULT_CLOSE_TO_FINISH_THRESHOLD_DAYS,
    DEFAULT_EXPIRY_THRESHOLD_DAYS,
    DEFAULT_MIN_PACKAGE_COUNT,
)

_USER_ID = uuid4()


class TestGetEffectivePreferences:
    async def test_returns_defaults_when_no_row_exists(
        self, mock_session: AsyncMock, mocker: MockerFixture
    ):
        mocker.patch(
            "app.api.v1.users.service.crud.get_user_preferences",
            autospec=True,
            return_value=None,
        )

        result = await get_effective_preferences(session=mock_session, user_id=_USER_ID)

        assert isinstance(result, UserPreferencesOut)
        assert result.expiry_threshold_days == DEFAULT_EXPIRY_THRESHOLD_DAYS
        assert (
            result.close_to_finish_threshold_days
            == DEFAULT_CLOSE_TO_FINISH_THRESHOLD_DAYS
        )
        assert result.min_package_count == DEFAULT_MIN_PACKAGE_COUNT

    async def test_returns_stored_values_when_row_exists(
        self, mock_session: AsyncMock, mocker: MockerFixture
    ):
        prefs = MagicMock(spec=UserPreferences)
        prefs.expiry_threshold_days = 14
        prefs.close_to_finish_threshold_days = 3
        prefs.min_package_count = 5
        mocker.patch(
            "app.api.v1.users.service.crud.get_user_preferences",
            autospec=True,
            return_value=prefs,
        )

        result = await get_effective_preferences(session=mock_session, user_id=_USER_ID)

        assert isinstance(result, UserPreferencesOut)
        assert result.expiry_threshold_days == 14
        assert result.close_to_finish_threshold_days == 3
        assert result.min_package_count == 5


class TestUpdatePreferences:
    async def test_updates_existing_row(
        self, mock_session: AsyncMock, mocker: MockerFixture
    ):
        existing = MagicMock(spec=UserPreferences)
        updated = MagicMock(spec=UserPreferences)
        updated.expiry_threshold_days = DEFAULT_EXPIRY_THRESHOLD_DAYS
        updated.close_to_finish_threshold_days = DEFAULT_CLOSE_TO_FINISH_THRESHOLD_DAYS
        updated.min_package_count = 3
        mocker.patch(
            "app.api.v1.users.service.crud.get_user_preferences",
            autospec=True,
            return_value=existing,
        )
        mocker.patch(
            "app.api.v1.users.service.crud.update_preferences",
            autospec=True,
            return_value=updated,
        )

        result = await update_preferences(
            session=mock_session,
            user_id=_USER_ID,
            expiry_threshold_days=DEFAULT_EXPIRY_THRESHOLD_DAYS,
            close_to_finish_threshold_days=DEFAULT_CLOSE_TO_FINISH_THRESHOLD_DAYS,
            min_package_count=3,
        )

        assert isinstance(result, UserPreferencesOut)
        assert result.min_package_count == 3

    async def test_inserts_new_row_when_none_exists(
        self, mock_session: AsyncMock, mocker: MockerFixture
    ):
        inserted = MagicMock(spec=UserPreferences)
        inserted.expiry_threshold_days = DEFAULT_EXPIRY_THRESHOLD_DAYS
        inserted.close_to_finish_threshold_days = DEFAULT_CLOSE_TO_FINISH_THRESHOLD_DAYS
        inserted.min_package_count = 5
        mocker.patch(
            "app.api.v1.users.service.crud.get_user_preferences",
            autospec=True,
            return_value=None,
        )
        insert_mock = mocker.patch(
            "app.api.v1.users.service.crud.insert_preferences",
            autospec=True,
            return_value=inserted,
        )

        result = await update_preferences(
            session=mock_session,
            user_id=_USER_ID,
            expiry_threshold_days=DEFAULT_EXPIRY_THRESHOLD_DAYS,
            close_to_finish_threshold_days=DEFAULT_CLOSE_TO_FINISH_THRESHOLD_DAYS,
            min_package_count=5,
        )

        assert isinstance(result, UserPreferencesOut)
        assert result.min_package_count == 5
        insert_mock.assert_awaited_once()


class TestDeleteUserRows:
    async def test_delegates_to_crud(
        self, mock_session: AsyncMock, mocker: MockerFixture
    ):
        crud_mock = mocker.patch(
            "app.api.v1.users.service.crud.delete_user_rows",
            autospec=True,
            return_value=None,
        )

        await delete_user_rows(session=mock_session, user_id=_USER_ID)

        crud_mock.assert_awaited_once_with(session=mock_session, user_id=_USER_ID)
