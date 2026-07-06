"""Integration tests for users router (HTTP contract, hermetic — no live DB)."""

import pytest
from fastapi import status
from httpx import AsyncClient
from pytest_mock import MockerFixture

from app.api.v1.users.schemas import UserPreferencesOut
from app.utilities.const import (
    DEFAULT_CLOSE_TO_FINISH_THRESHOLD_DAYS,
    DEFAULT_EXPIRY_THRESHOLD_DAYS,
)
from app.utilities.errors import (
    AccountDeletionError,
    CabinetDatabaseError,
    UserDatabaseError,
)

PREFERENCES_URL = "/api/v1/users/preferences"
DELETE_ACCOUNT_URL = "/api/v1/users/me"

_STORED_PREFS = UserPreferencesOut(
    expiry_threshold_days=14,
    close_to_finish_threshold_days=3,
    min_package_count=5,
)


class TestGetPreferencesEndpoint:
    async def test_missing_token_returns_401_or_403(self, client: AsyncClient):
        response = await client.get(PREFERENCES_URL)
        assert response.status_code in (
            status.HTTP_401_UNAUTHORIZED,
            status.HTTP_403_FORBIDDEN,
        )

    async def test_serializes_service_result(
        self, authed_client: AsyncClient, mocker: MockerFixture
    ):
        mocker.patch(
            "app.api.v1.users.router.users_service.get_effective_preferences",
            autospec=True,
            return_value=_STORED_PREFS,
        )

        response = await authed_client.get(PREFERENCES_URL)

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["expiry_threshold_days"] == 14
        assert data["close_to_finish_threshold_days"] == 3
        assert data["min_package_count"] == 5

    async def test_db_error_returns_503(
        self, authed_client: AsyncClient, mocker: MockerFixture
    ):
        mocker.patch(
            "app.api.v1.users.router.users_service.get_effective_preferences",
            autospec=True,
            side_effect=UserDatabaseError(),
        )

        response = await authed_client.get(PREFERENCES_URL)

        assert response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE


class TestPatchPreferencesEndpoint:
    def _make_prefs_out(self, min_package_count: int) -> UserPreferencesOut:
        return UserPreferencesOut(
            expiry_threshold_days=DEFAULT_EXPIRY_THRESHOLD_DAYS,
            close_to_finish_threshold_days=DEFAULT_CLOSE_TO_FINISH_THRESHOLD_DAYS,
            min_package_count=min_package_count,
        )

    async def test_updates_min_package_count(
        self, authed_client: AsyncClient, mocker: MockerFixture
    ):
        mocker.patch(
            "app.api.v1.users.router.users_service.update_preferences",
            autospec=True,
            return_value=self._make_prefs_out(min_package_count=3),
        )

        response = await authed_client.patch(
            PREFERENCES_URL, json={"min_package_count": 3}
        )

        assert response.status_code == status.HTTP_200_OK
        assert response.json()["min_package_count"] == 3

    async def test_db_error_returns_503(
        self, authed_client: AsyncClient, mocker: MockerFixture
    ):
        mocker.patch(
            "app.api.v1.users.router.users_service.update_preferences",
            autospec=True,
            side_effect=UserDatabaseError(),
        )

        response = await authed_client.patch(
            PREFERENCES_URL, json={"min_package_count": 3}
        )

        assert response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE

    @pytest.mark.parametrize("invalid_value", [0, 11])
    async def test_out_of_range_returns_422(
        self, authed_client: AsyncClient, invalid_value: int
    ):
        response = await authed_client.patch(
            PREFERENCES_URL, json={"min_package_count": invalid_value}
        )

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT

    async def test_missing_token_returns_401_or_403(self, client: AsyncClient):
        response = await client.patch(PREFERENCES_URL, json={"min_package_count": 3})
        assert response.status_code in (
            status.HTTP_401_UNAUTHORIZED,
            status.HTTP_403_FORBIDDEN,
        )


class TestDeleteAccountEndpoint:
    async def test_missing_token_returns_401_or_403(self, client: AsyncClient):
        response = await client.delete(DELETE_ACCOUNT_URL)
        assert response.status_code in (
            status.HTTP_401_UNAUTHORIZED,
            status.HTTP_403_FORBIDDEN,
        )

    async def test_success_returns_204(
        self, authed_client: AsyncClient, mocker: MockerFixture
    ):
        mocker.patch(
            "app.api.v1.users.router.users_facade.delete_account",
            autospec=True,
            return_value=None,
        )

        response = await authed_client.delete(DELETE_ACCOUNT_URL)

        assert response.status_code == status.HTTP_204_NO_CONTENT

    async def test_user_database_error_returns_503(
        self, authed_client: AsyncClient, mocker: MockerFixture
    ):
        mocker.patch(
            "app.api.v1.users.router.users_facade.delete_account",
            autospec=True,
            side_effect=UserDatabaseError(),
        )

        response = await authed_client.delete(DELETE_ACCOUNT_URL)

        assert response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE

    async def test_cabinet_database_error_returns_503(
        self, authed_client: AsyncClient, mocker: MockerFixture
    ):
        mocker.patch(
            "app.api.v1.users.router.users_facade.delete_account",
            autospec=True,
            side_effect=CabinetDatabaseError(),
        )

        response = await authed_client.delete(DELETE_ACCOUNT_URL)

        assert response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE

    async def test_account_deletion_error_returns_502(
        self, authed_client: AsyncClient, mocker: MockerFixture
    ):
        mocker.patch(
            "app.api.v1.users.router.users_facade.delete_account",
            autospec=True,
            side_effect=AccountDeletionError(),
        )

        response = await authed_client.delete(DELETE_ACCOUNT_URL)

        assert response.status_code == status.HTTP_502_BAD_GATEWAY
