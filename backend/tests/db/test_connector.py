"""Unit tests for connector.py context managers (no live DB)."""

from unittest.mock import AsyncMock, MagicMock, call

import pytest
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.connector import persist


def _make_session() -> AsyncMock:
    return AsyncMock(spec=AsyncSession)


class TestPersist:
    async def test_flushes_refreshes_and_commits_on_success(self):
        session = _make_session()
        instance = MagicMock()

        async with persist(session, instance):
            pass

        session.flush.assert_awaited_once()
        session.refresh.assert_awaited_once_with(instance)
        session.commit.assert_awaited_once()
        session.rollback.assert_not_awaited()

    async def test_refreshes_all_instances_in_order(self):
        session = _make_session()
        a, b, c = MagicMock(), MagicMock(), MagicMock()

        async with persist(session, a, b, c):
            pass

        assert session.refresh.await_args_list == [call(a), call(b), call(c)]

    async def test_no_instances_still_flushes_and_commits(self):
        session = _make_session()

        async with persist(session):
            pass

        session.flush.assert_awaited_once()
        session.commit.assert_awaited_once()
        session.refresh.assert_not_awaited()

    async def test_rolls_back_and_reraises_on_flush_error(self):
        session = _make_session()
        session.flush.side_effect = SQLAlchemyError("disk full")

        with pytest.raises(SQLAlchemyError):
            async with persist(session, MagicMock()):
                pass

        session.rollback.assert_awaited_once()
        session.commit.assert_not_awaited()

    async def test_rolls_back_and_reraises_on_commit_error(self):
        session = _make_session()
        session.commit.side_effect = SQLAlchemyError("connection lost")

        with pytest.raises(SQLAlchemyError):
            async with persist(session, MagicMock()):
                pass

        session.rollback.assert_awaited_once()

    async def test_rolls_back_and_reraises_on_exception_inside_block(self):
        session = _make_session()

        with pytest.raises(ValueError, match="boom"):
            async with persist(session, MagicMock()):
                raise ValueError("boom")

        session.rollback.assert_awaited_once()
        session.flush.assert_not_awaited()
        session.commit.assert_not_awaited()

    async def test_original_exception_is_reraised_unchanged(self):
        session = _make_session()
        original = SQLAlchemyError("original")
        session.flush.side_effect = original

        with pytest.raises(SQLAlchemyError) as exc_info:
            async with persist(session, MagicMock()):
                pass

        assert exc_info.value is original
