"""Integration tests for auth router endpoints (HTTP contract, hermetic — no live DB or Supabase)."""

from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import jwt
import pytest
from fastapi import status
from httpx import AsyncClient
from pytest_mock import MockerFixture

from app.api.v1.auth.schemas import AuthResponse, UserOut
from app.utilities.errors import (
    DuplicateEmailError,
    InvalidCredentialsError,
    InvalidEmailError,
    ProvisioningError,
    RateLimitError,
    RegistrationError,
    SessionExpiredError,
    WeakPasswordError,
)

_FAKE_USER_ID = uuid4()
_FAKE_EMAIL = "test@example.com"
_FAKE_ACCESS_TOKEN = "fake.access.token"
_FAKE_REFRESH_TOKEN = "fake-refresh-token"


def _fake_auth_response() -> tuple[AuthResponse, str]:
    return (
        AuthResponse(
            access_token=_FAKE_ACCESS_TOKEN,
            user=UserOut(id=_FAKE_USER_ID, email=_FAKE_EMAIL),
        ),
        _FAKE_REFRESH_TOKEN,
    )


class TestAuthGuard:
    @pytest.mark.asyncio
    async def test_missing_token_returns_401_or_403(self, client: AsyncClient):
        response = await client.get("/api/v1/auth/me")
        assert response.status_code in (
            status.HTTP_401_UNAUTHORIZED,
            status.HTTP_403_FORBIDDEN,
        )

    @pytest.mark.asyncio
    async def test_invalid_token_returns_401(self, client: AsyncClient):
        response = await client.get(
            "/api/v1/auth/me", headers={"Authorization": "Bearer not.a.real.token"}
        )
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    @pytest.mark.asyncio
    async def test_valid_token_returns_200_with_user(
        self, client: AsyncClient, mocker: MockerFixture
    ):
        fake_claims = {
            "sub": str(_FAKE_USER_ID),
            "email": _FAKE_EMAIL,
            "aud": "authenticated",
        }
        mock_jwks = mocker.patch("app.core.jwt_security._jwks")
        mocker.patch("app.core.jwt_security.jwt.decode", return_value=fake_claims)
        mock_signing_key = MagicMock()
        mock_signing_key.key = "fake-key"
        mock_jwks.get_signing_key_from_jwt.return_value = mock_signing_key

        response = await client.get(
            "/api/v1/auth/me", headers={"Authorization": "Bearer valid.token.here"}
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["email"] == _FAKE_EMAIL
        assert data["id"] == str(_FAKE_USER_ID)

    @pytest.mark.asyncio
    async def test_wrong_audience_returns_401(
        self, client: AsyncClient, mocker: MockerFixture
    ):
        mock_jwks = mocker.patch("app.core.jwt_security._jwks")
        mocker.patch(
            "app.core.jwt_security.jwt.decode",
            side_effect=jwt.InvalidAudienceError("Invalid audience"),
        )
        mock_signing_key = MagicMock()
        mock_signing_key.key = "fake-key"
        mock_jwks.get_signing_key_from_jwt.return_value = mock_signing_key

        response = await client.get(
            "/api/v1/auth/me", headers={"Authorization": "Bearer wrong.audience.token"}
        )

        assert response.status_code == status.HTTP_401_UNAUTHORIZED
        assert "audience" in response.json()["detail"].lower()


class TestRegisterEndpoint:
    @pytest.mark.asyncio
    async def test_success_returns_201_with_token_and_cookie(
        self, client: AsyncClient, mocker: MockerFixture
    ):
        mock_register = mocker.patch(
            "app.api.v1.auth.router.auth_service.register",
            new_callable=AsyncMock,
            return_value=_fake_auth_response(),
        )

        response = await client.post(
            "/api/v1/auth/register",
            json={"email": _FAKE_EMAIL, "password": "securepassword123"},
        )

        assert response.status_code == status.HTTP_201_CREATED
        data = response.json()
        assert data["access_token"] == _FAKE_ACCESS_TOKEN
        assert data["token_type"] == "bearer"
        assert data["user"]["email"] == _FAKE_EMAIL
        assert "refresh_token" in response.cookies
        mock_register.assert_called_once()

    @pytest.mark.asyncio
    async def test_duplicate_email_returns_409(
        self, client: AsyncClient, mocker: MockerFixture
    ):
        mocker.patch(
            "app.api.v1.auth.router.auth_service.register",
            new_callable=AsyncMock,
            side_effect=DuplicateEmailError(),
        )

        response = await client.post(
            "/api/v1/auth/register",
            json={"email": _FAKE_EMAIL, "password": "securepassword123"},
        )

        assert response.status_code == status.HTTP_409_CONFLICT
        assert "already exists" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_weak_password_returns_422(
        self, client: AsyncClient, mocker: MockerFixture
    ):
        mocker.patch(
            "app.api.v1.auth.router.auth_service.register",
            new_callable=AsyncMock,
            side_effect=WeakPasswordError(),
        )

        response = await client.post(
            "/api/v1/auth/register",
            json={"email": _FAKE_EMAIL, "password": "securepassword123"},
        )

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
        assert "weak" in response.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_invalid_email_returns_422(
        self, client: AsyncClient, mocker: MockerFixture
    ):
        mocker.patch(
            "app.api.v1.auth.router.auth_service.register",
            new_callable=AsyncMock,
            side_effect=InvalidEmailError(),
        )

        response = await client.post(
            "/api/v1/auth/register",
            json={"email": _FAKE_EMAIL, "password": "securepassword123"},
        )

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
        assert "invalid" in response.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_registration_error_returns_400(
        self, client: AsyncClient, mocker: MockerFixture
    ):
        mocker.patch(
            "app.api.v1.auth.router.auth_service.register",
            new_callable=AsyncMock,
            side_effect=RegistrationError(),
        )

        response = await client.post(
            "/api/v1/auth/register",
            json={"email": _FAKE_EMAIL, "password": "securepassword123"},
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST

    @pytest.mark.asyncio
    async def test_provisioning_error_returns_500(
        self, client: AsyncClient, mocker: MockerFixture
    ):
        mocker.patch(
            "app.api.v1.auth.router.auth_service.register",
            new_callable=AsyncMock,
            side_effect=ProvisioningError(),
        )

        response = await client.post(
            "/api/v1/auth/register",
            json={"email": _FAKE_EMAIL, "password": "securepassword123"},
        )

        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR

    @pytest.mark.asyncio
    async def test_rate_limit_returns_429(
        self, client: AsyncClient, mocker: MockerFixture
    ):
        mocker.patch(
            "app.api.v1.auth.router.auth_service.register",
            new_callable=AsyncMock,
            side_effect=RateLimitError(),
        )

        response = await client.post(
            "/api/v1/auth/register",
            json={"email": _FAKE_EMAIL, "password": "securepassword123"},
        )

        assert response.status_code == status.HTTP_429_TOO_MANY_REQUESTS


class TestLoginEndpoint:
    @pytest.mark.asyncio
    async def test_success_returns_200_with_token_and_cookie(
        self, client: AsyncClient, mocker: MockerFixture
    ):
        mock_login = mocker.patch(
            "app.api.v1.auth.router.auth_service.login",
            new_callable=AsyncMock,
            return_value=_fake_auth_response(),
        )

        response = await client.post(
            "/api/v1/auth/login",
            json={"email": _FAKE_EMAIL, "password": "securepassword123"},
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["access_token"] == _FAKE_ACCESS_TOKEN
        assert "refresh_token" in response.cookies
        mock_login.assert_called_once()

    @pytest.mark.asyncio
    async def test_invalid_credentials_returns_401(
        self, client: AsyncClient, mocker: MockerFixture
    ):
        mocker.patch(
            "app.api.v1.auth.router.auth_service.login",
            new_callable=AsyncMock,
            side_effect=InvalidCredentialsError(),
        )

        response = await client.post(
            "/api/v1/auth/login",
            json={"email": _FAKE_EMAIL, "password": "wrongpassword"},
        )

        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    @pytest.mark.asyncio
    async def test_rate_limit_returns_429(
        self, client: AsyncClient, mocker: MockerFixture
    ):
        mocker.patch(
            "app.api.v1.auth.router.auth_service.login",
            new_callable=AsyncMock,
            side_effect=RateLimitError(),
        )

        response = await client.post(
            "/api/v1/auth/login",
            json={"email": _FAKE_EMAIL, "password": "securepassword123"},
        )

        assert response.status_code == status.HTTP_429_TOO_MANY_REQUESTS

    @pytest.mark.asyncio
    async def test_provisioning_error_returns_500(
        self, client: AsyncClient, mocker: MockerFixture
    ):
        mocker.patch(
            "app.api.v1.auth.router.auth_service.login",
            new_callable=AsyncMock,
            side_effect=ProvisioningError(),
        )

        response = await client.post(
            "/api/v1/auth/login",
            json={"email": _FAKE_EMAIL, "password": "securepassword123"},
        )

        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR


class TestRefreshEndpoint:
    @pytest.mark.asyncio
    async def test_valid_cookie_returns_200_with_new_token(
        self, client: AsyncClient, mocker: MockerFixture
    ):
        mocker.patch(
            "app.api.v1.auth.router.auth_service.refresh",
            return_value=_fake_auth_response(),
        )
        client.cookies.set("refresh_token", _FAKE_REFRESH_TOKEN)

        response = await client.get("/api/v1/auth/refresh")

        assert response.status_code == status.HTTP_200_OK
        assert response.json()["access_token"] == _FAKE_ACCESS_TOKEN

    @pytest.mark.asyncio
    async def test_missing_cookie_returns_401(self, client: AsyncClient):
        response = await client.get("/api/v1/auth/refresh", cookies={})
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    @pytest.mark.asyncio
    async def test_expired_session_returns_401(
        self, client: AsyncClient, mocker: MockerFixture
    ):
        mocker.patch(
            "app.api.v1.auth.router.auth_service.refresh",
            side_effect=SessionExpiredError(),
        )
        client.cookies.set("refresh_token", _FAKE_REFRESH_TOKEN)

        response = await client.get("/api/v1/auth/refresh")

        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    @pytest.mark.asyncio
    async def test_rate_limit_returns_429(
        self, client: AsyncClient, mocker: MockerFixture
    ):
        mocker.patch(
            "app.api.v1.auth.router.auth_service.refresh",
            side_effect=RateLimitError(),
        )
        client.cookies.set("refresh_token", _FAKE_REFRESH_TOKEN)

        response = await client.get("/api/v1/auth/refresh")

        assert response.status_code == status.HTTP_429_TOO_MANY_REQUESTS


class TestLogoutEndpoint:
    @pytest.mark.asyncio
    async def test_clears_refresh_cookie(
        self, client: AsyncClient, mocker: MockerFixture
    ):
        fake_claims = {
            "sub": str(_FAKE_USER_ID),
            "email": _FAKE_EMAIL,
            "aud": "authenticated",
        }
        mock_jwks = mocker.patch("app.core.jwt_security._jwks")
        mocker.patch("app.core.jwt_security.jwt.decode", return_value=fake_claims)
        mocker.patch("app.db.supabase_auth.get_supabase")
        mock_signing_key = MagicMock()
        mock_signing_key.key = "fake-key"
        mock_jwks.get_signing_key_from_jwt.return_value = mock_signing_key

        response = await client.post(
            "/api/v1/auth/logout",
            headers={"Authorization": "Bearer valid.token.here"},
        )

        assert response.status_code == status.HTTP_204_NO_CONTENT
        set_cookie = response.headers.get("set-cookie", "")
        assert "refresh_token" in set_cookie
        assert "Max-Age=0" in set_cookie
