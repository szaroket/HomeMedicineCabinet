"""Integration tests for users router (HTTP contract, hermetic — no live DB)."""

from fastapi import status
from httpx import AsyncClient
from pytest_mock import MockerFixture

from app.api.v1.users.schemas import UserPreferencesOut
from app.utilities.errors import UserDatabaseError

PREFERENCES_URL = "/api/v1/users/preferences"

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
