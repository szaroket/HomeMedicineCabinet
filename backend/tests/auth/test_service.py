"""Unit tests for auth service layer (business logic, no HTTP, no live DB or Supabase)."""

from unittest.mock import AsyncMock, MagicMock
from uuid import UUID, uuid4

import pytest
from pytest_mock import MockerFixture

from app.api.v1.auth.schemas import LoginRequest, RegisterRequest
from app.api.v1.auth.service import login, refresh, register
from app.utilities.errors import (
    DuplicateEmailError,
    InvalidCredentialsError,
    RegistrationError,
    SessionExpiredError,
)

_FAKE_USER_ID = uuid4()
_FAKE_EMAIL = "test@example.com"
_FAKE_ACCESS_TOKEN = "fake.access.token"
_FAKE_REFRESH_TOKEN = "fake-refresh-token"


def _mock_supabase_result(
    user_id: UUID = _FAKE_USER_ID,
    email: str = _FAKE_EMAIL,
    access_token: str = _FAKE_ACCESS_TOKEN,
    refresh_token: str = _FAKE_REFRESH_TOKEN,
) -> MagicMock:
    user = MagicMock()
    user.id = str(user_id)
    user.email = email

    session = MagicMock()
    session.access_token = access_token
    session.refresh_token = refresh_token

    result = MagicMock()
    result.user = user
    result.session = session
    return result


class TestRegisterService:
    @pytest.mark.asyncio
    async def test_success_returns_auth_response_and_refresh_token(
        self, mocker: MockerFixture
    ):
        mock_session = AsyncMock()
        data = RegisterRequest(email=_FAKE_EMAIL, password="securepassword123")
        mocker.patch(
            "app.api.v1.auth.service.supabase_auth.sign_up",
            return_value=_mock_supabase_result(),
        )
        mock_provision = mocker.patch(
            "app.api.v1.auth.service.crud.provision_user", new_callable=AsyncMock
        )

        auth_response, returned_refresh_token = await register(mock_session, data)

        assert auth_response.access_token == _FAKE_ACCESS_TOKEN
        assert auth_response.user.email == _FAKE_EMAIL
        assert auth_response.user.id == _FAKE_USER_ID
        assert returned_refresh_token == _FAKE_REFRESH_TOKEN
        mock_provision.assert_awaited_once_with(
            mock_session, _FAKE_USER_ID, _FAKE_EMAIL
        )

    @pytest.mark.asyncio
    async def test_no_user_in_result_raises_duplicate_email_error(
        self, mocker: MockerFixture
    ):
        mock_session = AsyncMock()
        data = RegisterRequest(email=_FAKE_EMAIL, password="securepassword123")
        result = _mock_supabase_result()
        result.user = None
        mocker.patch(
            "app.api.v1.auth.service.supabase_auth.sign_up", return_value=result
        )

        with pytest.raises(DuplicateEmailError):
            await register(mock_session, data)

    @pytest.mark.asyncio
    async def test_no_session_in_result_raises_registration_error(
        self, mocker: MockerFixture
    ):
        mock_session = AsyncMock()
        data = RegisterRequest(email=_FAKE_EMAIL, password="securepassword123")
        result = _mock_supabase_result()
        result.session = None
        mocker.patch(
            "app.api.v1.auth.service.supabase_auth.sign_up", return_value=result
        )

        with pytest.raises(RegistrationError):
            await register(mock_session, data)

    @pytest.mark.asyncio
    async def test_supabase_error_propagates(self, mocker: MockerFixture):
        mock_session = AsyncMock()
        data = RegisterRequest(email=_FAKE_EMAIL, password="securepassword123")
        mocker.patch(
            "app.api.v1.auth.service.supabase_auth.sign_up",
            side_effect=DuplicateEmailError(),
        )

        with pytest.raises(DuplicateEmailError):
            await register(mock_session, data)


class TestLoginService:
    @pytest.mark.asyncio
    async def test_success_returns_auth_response_and_refresh_token(
        self, mocker: MockerFixture
    ):
        mock_session = AsyncMock()
        data = LoginRequest(email=_FAKE_EMAIL, password="securepassword123")
        mocker.patch(
            "app.api.v1.auth.service.supabase_auth.sign_in_with_password",
            return_value=_mock_supabase_result(),
        )
        mock_provision = mocker.patch(
            "app.api.v1.auth.service.crud.provision_user", new_callable=AsyncMock
        )

        auth_response, returned_refresh_token = await login(mock_session, data)

        assert auth_response.access_token == _FAKE_ACCESS_TOKEN
        assert auth_response.user.email == _FAKE_EMAIL
        assert returned_refresh_token == _FAKE_REFRESH_TOKEN
        mock_provision.assert_awaited_once_with(
            mock_session, _FAKE_USER_ID, _FAKE_EMAIL
        )

    @pytest.mark.asyncio
    async def test_no_user_or_session_raises_invalid_credentials(
        self, mocker: MockerFixture
    ):
        mock_session = AsyncMock()
        data = LoginRequest(email=_FAKE_EMAIL, password="securepassword123")
        result = _mock_supabase_result()
        result.user = None
        mocker.patch(
            "app.api.v1.auth.service.supabase_auth.sign_in_with_password",
            return_value=result,
        )

        with pytest.raises(InvalidCredentialsError):
            await login(mock_session, data)

    @pytest.mark.asyncio
    async def test_supabase_error_propagates(self, mocker: MockerFixture):
        mock_session = AsyncMock()
        data = LoginRequest(email=_FAKE_EMAIL, password="securepassword123")
        mocker.patch(
            "app.api.v1.auth.service.supabase_auth.sign_in_with_password",
            side_effect=InvalidCredentialsError(),
        )

        with pytest.raises(InvalidCredentialsError):
            await login(mock_session, data)


class TestRefreshService:
    def test_success_returns_auth_response_and_new_refresh_token(
        self, mocker: MockerFixture
    ):
        new_refresh = "new-refresh-token"
        mocker.patch(
            "app.api.v1.auth.service.supabase_auth.refresh_session",
            return_value=_mock_supabase_result(refresh_token=new_refresh),
        )

        auth_response, returned_refresh_token = refresh(_FAKE_REFRESH_TOKEN)

        assert auth_response.access_token == _FAKE_ACCESS_TOKEN
        assert returned_refresh_token == new_refresh

    def test_no_user_or_session_raises_session_expired(self, mocker: MockerFixture):
        result = _mock_supabase_result()
        result.session = None
        mocker.patch(
            "app.api.v1.auth.service.supabase_auth.refresh_session", return_value=result
        )

        with pytest.raises(SessionExpiredError):
            refresh(_FAKE_REFRESH_TOKEN)

    def test_supabase_error_propagates(self, mocker: MockerFixture):
        mocker.patch(
            "app.api.v1.auth.service.supabase_auth.refresh_session",
            side_effect=SessionExpiredError(),
        )

        with pytest.raises(SessionExpiredError):
            refresh(_FAKE_REFRESH_TOKEN)
