"""Unit tests for the Supabase admin client and delete_user operation."""

from unittest.mock import MagicMock

import pytest
from pytest_mock import MockerFixture
from supabase import AuthApiError

import app.db.supabase_auth as supabase_auth
from app.db.supabase_auth import delete_user, get_supabase_admin
from app.utilities.errors import AccountDeletionError

_FAKE_USER_ID = "11111111-1111-1111-1111-111111111111"


@pytest.fixture(autouse=True)
def _reset_admin_client():
    supabase_auth._admin_client = None
    yield
    supabase_auth._admin_client = None


class TestGetSupabaseAdmin:
    def test_creates_client_with_service_role_key(self, mocker: MockerFixture):
        mock_create_client = mocker.patch("app.db.supabase_auth.create_client")
        mocker.patch(
            "app.db.supabase_auth.settings.supabase_url", "https://project.supabase.co"
        )
        mocker.patch(
            "app.db.supabase_auth.settings.supabase_service_role_key", "srv-key"
        )

        get_supabase_admin()

        mock_create_client.assert_called_once_with(
            "https://project.supabase.co", "srv-key"
        )

    def test_caches_client_across_calls(self, mocker: MockerFixture):
        mock_create_client = mocker.patch("app.db.supabase_auth.create_client")

        first = get_supabase_admin()
        second = get_supabase_admin()

        assert first is second
        mock_create_client.assert_called_once()


class TestDeleteUser:
    def test_success_calls_admin_delete_user_with_id(self, mocker: MockerFixture):
        mock_admin_client = MagicMock()
        mocker.patch(
            "app.db.supabase_auth.get_supabase_admin", return_value=mock_admin_client
        )

        delete_user(_FAKE_USER_ID)

        mock_admin_client.auth.admin.delete_user.assert_called_once_with(_FAKE_USER_ID)

    def test_auth_api_error_maps_to_account_deletion_error(self, mocker: MockerFixture):
        mock_admin_client = MagicMock()
        mock_admin_client.auth.admin.delete_user.side_effect = AuthApiError(
            "boom", 500, "unexpected_failure"
        )
        mocker.patch(
            "app.db.supabase_auth.get_supabase_admin", return_value=mock_admin_client
        )

        with pytest.raises(AccountDeletionError):
            delete_user(_FAKE_USER_ID)

    def test_user_not_found_is_treated_as_already_deleted(self, mocker: MockerFixture):
        mock_admin_client = MagicMock()
        mock_admin_client.auth.admin.delete_user.side_effect = AuthApiError(
            "not found", 404, "user_not_found"
        )
        mocker.patch(
            "app.db.supabase_auth.get_supabase_admin", return_value=mock_admin_client
        )

        delete_user(_FAKE_USER_ID)

    def test_unexpected_exception_maps_to_account_deletion_error(
        self, mocker: MockerFixture
    ):
        mock_admin_client = MagicMock()
        mock_admin_client.auth.admin.delete_user.side_effect = RuntimeError("boom")
        mocker.patch(
            "app.db.supabase_auth.get_supabase_admin", return_value=mock_admin_client
        )

        with pytest.raises(AccountDeletionError):
            delete_user(_FAKE_USER_ID)
