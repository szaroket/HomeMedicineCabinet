"""Shared fixtures for hermetic backend tests (no live DB or Supabase).

Provides HTTPX clients with FastAPI dependencies overridden:

* ``client`` overrides only ``get_session`` — use for public endpoints and for
  exercising the real auth guard (e.g. a missing-token case).
* ``authed_client`` also overrides ``get_current_user`` — use for endpoints
  protected by ``Security(get_current_user)``.

DB-backed integration tests use the ``db_session`` fixture in
``tests/db/conftest.py`` instead.
"""

from collections.abc import AsyncIterator
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.auth.types import CurrentUser
from app.core.jwt_security import get_current_user
from app.db.connector import get_session
from app.main import app


@pytest.fixture
def mock_session() -> AsyncMock:
    """A stand-in async DB session injected in place of ``get_session``."""
    return AsyncMock(spec=AsyncSession)


@pytest.fixture
def fake_user() -> CurrentUser:
    """The authenticated user injected by ``authed_client``."""
    return CurrentUser(id=uuid4(), email="test@example.com")


@pytest_asyncio.fixture
async def client(mock_session: AsyncMock) -> AsyncIterator[AsyncClient]:
    """Async HTTPX client with only the DB session dependency overridden.

    The auth guard runs for real, so requests to protected routes without a
    valid token are rejected — use this to test public endpoints and guards.
    """

    async def override_get_session():
        yield mock_session

    app.dependency_overrides[get_session] = override_get_session
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as c:
        yield c
    app.dependency_overrides.pop(get_session, None)


@pytest_asyncio.fixture
async def authed_client(
    mock_session: AsyncMock, fake_user: CurrentUser
) -> AsyncIterator[AsyncClient]:
    """Async HTTPX client with both DB session and auth guard overridden.

    Every request is treated as ``fake_user``; use this for endpoints protected
    by ``Security(get_current_user)``.
    """

    async def override_get_session():
        yield mock_session

    app.dependency_overrides[get_session] = override_get_session
    app.dependency_overrides[get_current_user] = lambda: fake_user
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as c:
        yield c
    app.dependency_overrides.pop(get_session, None)
    app.dependency_overrides.pop(get_current_user, None)
