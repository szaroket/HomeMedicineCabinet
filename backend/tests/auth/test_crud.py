"""Unit tests for auth CRUD layer (DB operations, no HTTP or Supabase)."""

from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from pytest_mock import MockerFixture
from sqlalchemy.exc import SQLAlchemyError

from app.api.v1.auth.crud import provision_user
from app.utilities.errors import ProvisioningError

_FAKE_USER_ID = uuid4()
_FAKE_EMAIL = "test@example.com"


class TestProvisionUser:
    @pytest.mark.asyncio
    async def test_success_executes_two_inserts_and_commits(
        self, mocker: MockerFixture
    ):
        mock_session = AsyncMock()
        mocker.patch("app.api.v1.auth.crud.insert")

        await provision_user(mock_session, _FAKE_USER_ID, _FAKE_EMAIL)

        assert mock_session.execute.await_count == 2
        mock_session.commit.assert_awaited_once()
        mock_session.rollback.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_db_error_rolls_back_and_raises_provisioning_error(self):
        mock_session = AsyncMock()
        mock_session.execute.side_effect = SQLAlchemyError("connection lost")

        with pytest.raises(ProvisioningError):
            await provision_user(mock_session, _FAKE_USER_ID, _FAKE_EMAIL)

        mock_session.rollback.assert_awaited_once()
        mock_session.commit.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_rollback_called_before_raising(self):
        """Verify rollback precedes the raise so no partial state leaks."""
        call_order: list[str] = []
        mock_session = AsyncMock()
        mock_session.execute.side_effect = SQLAlchemyError("boom")
        mock_session.rollback.side_effect = lambda: call_order.append("rollback")

        with pytest.raises(ProvisioningError):
            await provision_user(mock_session, _FAKE_USER_ID, _FAKE_EMAIL)

        assert call_order == ["rollback"]
