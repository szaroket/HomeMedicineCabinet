"""Unit tests for users facade: account-deletion cross-domain orchestration."""

from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from pytest_mock import MockerFixture

from app.api.v1.users.facade import delete_account
from app.utilities.errors import (
    AccountDeletionError,
    CabinetDatabaseError,
    UserDatabaseError,
)

_USER_ID = uuid4()


def _mock_persist(mocker: MockerFixture, side_effect=None):
    cm = MagicMock()
    cm.__aenter__ = AsyncMock(return_value=None)
    cm.__aexit__ = AsyncMock(return_value=False, side_effect=side_effect)
    return mocker.patch(
        "app.api.v1.users.facade.persist", return_value=cm, autospec=True
    )


@pytest.fixture
def mock_cabinet_service(mocker: MockerFixture):
    service = mocker.patch("app.api.v1.users.facade.cabinet_service", autospec=True)
    service.delete_by_user = AsyncMock(return_value=None)
    return service


@pytest.fixture
def mock_notifications_service(mocker: MockerFixture):
    service = mocker.patch(
        "app.api.v1.users.facade.notifications_service", autospec=True
    )
    service.delete_by_user = AsyncMock(return_value=None)
    return service


@pytest.fixture
def mock_users_service(mocker: MockerFixture):
    service = mocker.patch("app.api.v1.users.facade.users_service", autospec=True)
    service.delete_user_rows = AsyncMock(return_value=None)
    return service


@pytest.fixture
def mock_supabase_auth(mocker: MockerFixture):
    return mocker.patch("app.api.v1.users.facade.supabase_auth", autospec=True)


class TestDeleteAccount:
    async def test_local_deletes_run_before_supabase(
        self,
        mock_session: AsyncMock,
        mocker: MockerFixture,
        mock_cabinet_service,
        mock_notifications_service,
        mock_users_service,
        mock_supabase_auth,
    ):
        _mock_persist(mocker)

        await delete_account(session=mock_session, user_id=_USER_ID)

        mock_notifications_service.delete_by_user.assert_awaited_once_with(
            session=mock_session, user_id=_USER_ID
        )
        mock_cabinet_service.delete_by_user.assert_awaited_once_with(
            session=mock_session, user_id=_USER_ID
        )
        mock_users_service.delete_user_rows.assert_awaited_once_with(
            session=mock_session, user_id=_USER_ID
        )
        mock_supabase_auth.delete_user.assert_called_once_with(str(_USER_ID))

    async def test_cabinet_db_error_prevents_supabase_call(
        self,
        mock_session: AsyncMock,
        mocker: MockerFixture,
        mock_cabinet_service,
        mock_notifications_service,
        mock_users_service,
        mock_supabase_auth,
    ):
        mock_cabinet_service.delete_by_user.side_effect = CabinetDatabaseError()
        _mock_persist(mocker, side_effect=CabinetDatabaseError())

        with pytest.raises(CabinetDatabaseError):
            await delete_account(session=mock_session, user_id=_USER_ID)

        mock_supabase_auth.delete_user.assert_not_called()

    async def test_users_db_error_prevents_supabase_call(
        self,
        mock_session: AsyncMock,
        mocker: MockerFixture,
        mock_cabinet_service,
        mock_notifications_service,
        mock_users_service,
        mock_supabase_auth,
    ):
        mock_users_service.delete_user_rows.side_effect = UserDatabaseError()
        _mock_persist(mocker, side_effect=UserDatabaseError())

        with pytest.raises(UserDatabaseError):
            await delete_account(session=mock_session, user_id=_USER_ID)

        mock_supabase_auth.delete_user.assert_not_called()

    async def test_supabase_error_propagates_after_local_commit(
        self,
        mock_session: AsyncMock,
        mocker: MockerFixture,
        mock_cabinet_service,
        mock_notifications_service,
        mock_users_service,
        mock_supabase_auth,
    ):
        _mock_persist(mocker)
        mock_supabase_auth.delete_user.side_effect = AccountDeletionError()

        with pytest.raises(AccountDeletionError):
            await delete_account(session=mock_session, user_id=_USER_ID)

        mock_cabinet_service.delete_by_user.assert_awaited_once()
        mock_users_service.delete_user_rows.assert_awaited_once()
