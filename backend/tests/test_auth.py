"""Tests for auth guard and endpoints (hermetic — no live DB or Supabase)."""

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import jwt
import pytest
import pytest_asyncio
from fastapi import status
from httpx import ASGITransport, AsyncClient

from supabase import AuthApiError

from app.db.connector import get_session
from app.main import app

_FAKE_USER_ID = uuid4()
_FAKE_EMAIL = "test@example.com"
_FAKE_ACCESS_TOKEN = "fake.access.token"
_FAKE_REFRESH_TOKEN = "fake-refresh-token"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _mock_supabase_result() -> MagicMock:
    user = MagicMock()
    user.id = str(_FAKE_USER_ID)
    user.email = _FAKE_EMAIL

    session = MagicMock()
    session.access_token = _FAKE_ACCESS_TOKEN
    session.refresh_token = _FAKE_REFRESH_TOKEN

    result = MagicMock()
    result.user = user
    result.session = session
    return result


def _mock_jwks_ctx(fake_claims: dict):
    """Return a context manager pair that patches JWKS+decode."""
    return (
        patch("app.core.jwt_security._jwks"),
        patch("app.core.jwt_security.jwt.decode", return_value=fake_claims),
    )


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def client():
    """Async HTTPX client with DB session dependency overridden (no live DB)."""
    mock_session = AsyncMock()

    async def override_get_session():
        yield mock_session

    app.dependency_overrides[get_session] = override_get_session
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as c:
        yield c
    app.dependency_overrides.pop(get_session, None)


# ---------------------------------------------------------------------------
# Guard tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_guard_missing_token(client: AsyncClient):
    response = await client.get("/api/v1/auth/me")
    assert response.status_code in (
        status.HTTP_401_UNAUTHORIZED,
        status.HTTP_403_FORBIDDEN,
    )


@pytest.mark.asyncio
async def test_guard_invalid_token(client: AsyncClient):
    response = await client.get(
        "/api/v1/auth/me", headers={"Authorization": "Bearer not.a.real.token"}
    )
    assert response.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.asyncio
async def test_guard_valid_token(client: AsyncClient):
    """Valid token decoded via monkeypatched JWKS → 200 from /auth/me."""
    fake_claims = {
        "sub": str(_FAKE_USER_ID),
        "email": _FAKE_EMAIL,
        "aud": "authenticated",
    }
    jwks_patch, decode_patch = _mock_jwks_ctx(fake_claims)

    with jwks_patch as mock_jwks, decode_patch:
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
async def test_guard_wrong_audience(client: AsyncClient):
    """A token whose `aud` claim fails validation → 401 from the guard."""
    jwks_patch = patch("app.core.jwt_security._jwks")
    decode_patch = patch(
        "app.core.jwt_security.jwt.decode",
        side_effect=jwt.InvalidAudienceError("Invalid audience"),
    )

    with jwks_patch as mock_jwks, decode_patch:
        mock_signing_key = MagicMock()
        mock_signing_key.key = "fake-key"
        mock_jwks.get_signing_key_from_jwt.return_value = mock_signing_key

        response = await client.get(
            "/api/v1/auth/me",
            headers={"Authorization": "Bearer wrong.audience.token"},
        )

    assert response.status_code == status.HTTP_401_UNAUTHORIZED
    assert "audience" in response.json()["detail"].lower()


# ---------------------------------------------------------------------------
# Register endpoint
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_register_success(client: AsyncClient):
    """POST /auth/register returns access token, sets refresh cookie, provisions user."""
    supabase_result = _mock_supabase_result()

    with (
        patch("app.db.supabase_auth.get_supabase") as mock_get_sb,
        patch(
            "app.api.v1.auth.crud.provision_user", new_callable=AsyncMock
        ) as mock_provision,
    ):
        mock_get_sb.return_value.auth.sign_up.return_value = supabase_result

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
    mock_provision.assert_awaited_once()


@pytest.mark.asyncio
async def test_register_duplicate_email(client: AsyncClient):
    """POST /auth/register with user_already_exists code returns 409."""
    err = AuthApiError("User already registered", 400, None)
    err.code = "user_already_exists"

    with patch("app.db.supabase_auth.get_supabase") as mock_get_sb:
        mock_get_sb.return_value.auth.sign_up.side_effect = err

        response = await client.post(
            "/api/v1/auth/register",
            json={"email": _FAKE_EMAIL, "password": "securepassword123"},
        )

    assert response.status_code == status.HTTP_409_CONFLICT
    assert "already exists" in response.json()["detail"]


@pytest.mark.asyncio
async def test_register_weak_password(client: AsyncClient):
    """POST /auth/register with weak_password code returns 422."""
    err = AuthApiError("Password is too weak", 422, None)
    err.code = "weak_password"

    with patch("app.db.supabase_auth.get_supabase") as mock_get_sb:
        mock_get_sb.return_value.auth.sign_up.side_effect = err

        response = await client.post(
            "/api/v1/auth/register",
            json={"email": _FAKE_EMAIL, "password": "securepassword123"},
        )

    assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
    assert "weak" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_register_invalid_email(client: AsyncClient):
    """POST /auth/register with email_address_invalid code returns 422."""
    err = AuthApiError("Invalid email", 422, None)
    err.code = "email_address_invalid"

    with patch("app.db.supabase_auth.get_supabase") as mock_get_sb:
        mock_get_sb.return_value.auth.sign_up.side_effect = err

        response = await client.post(
            "/api/v1/auth/register",
            json={"email": _FAKE_EMAIL, "password": "securepassword123"},
        )

    assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
    assert "invalid" in response.json()["detail"].lower()


# ---------------------------------------------------------------------------
# Login endpoint
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_login_success(client: AsyncClient):
    """POST /auth/login returns access token and sets refresh cookie."""
    supabase_result = _mock_supabase_result()

    with (
        patch("app.db.supabase_auth.get_supabase") as mock_get_sb,
        patch("app.api.v1.auth.crud.provision_user", new_callable=AsyncMock),
    ):
        mock_get_sb.return_value.auth.sign_in_with_password.return_value = (
            supabase_result
        )

        response = await client.post(
            "/api/v1/auth/login",
            json={"email": _FAKE_EMAIL, "password": "securepassword123"},
        )

    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["access_token"] == _FAKE_ACCESS_TOKEN
    assert "refresh_token" in response.cookies


@pytest.mark.asyncio
async def test_login_invalid_credentials(client: AsyncClient):
    """POST /auth/login with wrong password returns 401."""
    with patch("app.db.supabase_auth.get_supabase") as mock_get_sb:
        mock_get_sb.return_value.auth.sign_in_with_password.side_effect = AuthApiError(
            "Invalid login credentials", 400, None
        )

        response = await client.post(
            "/api/v1/auth/login",
            json={"email": _FAKE_EMAIL, "password": "wrongpassword"},
        )

    assert response.status_code == status.HTTP_401_UNAUTHORIZED


# ---------------------------------------------------------------------------
# Refresh endpoint
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_refresh_with_cookie(client: AsyncClient):
    """GET /auth/refresh with a valid refresh cookie returns new access token."""
    supabase_result = _mock_supabase_result()

    with patch("app.db.supabase_auth.get_supabase") as mock_get_sb:
        mock_get_sb.return_value.auth.refresh_session.return_value = supabase_result

        client.cookies.set("refresh_token", _FAKE_REFRESH_TOKEN)
        response = await client.get("/api/v1/auth/refresh")

    assert response.status_code == status.HTTP_200_OK
    assert response.json()["access_token"] == _FAKE_ACCESS_TOKEN


@pytest.mark.asyncio
async def test_refresh_without_cookie(client: AsyncClient):
    """GET /auth/refresh without a cookie returns 401."""
    # ensure cookies are empty
    response = await client.get(
        "/api/v1/auth/refresh",
        cookies={},
    )
    assert response.status_code == status.HTTP_401_UNAUTHORIZED


# ---------------------------------------------------------------------------
# Logout endpoint
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_logout_clears_cookie(client: AsyncClient):
    """POST /auth/logout clears the refresh cookie."""
    fake_claims = {
        "sub": str(_FAKE_USER_ID),
        "email": _FAKE_EMAIL,
        "aud": "authenticated",
    }
    jwks_patch, decode_patch = _mock_jwks_ctx(fake_claims)

    with (
        jwks_patch as mock_jwks,
        decode_patch,
        patch("app.db.supabase_auth.get_supabase"),
    ):
        mock_signing_key = MagicMock()
        mock_signing_key.key = "fake-key"
        mock_jwks.get_signing_key_from_jwt.return_value = mock_signing_key

        response = await client.post(
            "/api/v1/auth/logout",
            headers={"Authorization": "Bearer valid.token.here"},
        )

    assert response.status_code == status.HTTP_204_NO_CONTENT
    set_cookie = response.headers.get("set-cookie", "")
    # Assert the cookie is actually being deleted, not merely present:
    # delete_cookie emits the cookie name with Max-Age=0.
    assert "refresh_token" in set_cookie
    assert "Max-Age=0" in set_cookie
