"""Unit tests for cabinet facade: cross-domain orchestration."""

from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from pytest_mock import MockerFixture

from app.api.v1.cabinet.facade import (
    list_entries,
    set_entry_importance,
    set_entry_quantity,
)
from app.api.v1.cabinet.schemas import CabinetPageOut

_USER_ID = uuid4()
_ENTRY_ID = uuid4()

_EMPTY_PAGE = CabinetPageOut(items=[], total=0, page=1, page_size=20)


@pytest.fixture
def mock_users_service(mocker: MockerFixture):
    svc = mocker.patch("app.api.v1.cabinet.facade.users_service", autospec=True)
    svc.get_user_preferences = AsyncMock(return_value=None)
    return svc


@pytest.fixture
def mock_cabinet_service(mocker: MockerFixture):
    svc = mocker.patch("app.api.v1.cabinet.facade.cabinet_service", autospec=True)
    svc.list_entries = AsyncMock(return_value=_EMPTY_PAGE)
    return svc


class TestFacadeListEntries:
    async def test_search_forwarded_to_service(
        self,
        mock_session: AsyncMock,
        mock_users_service,
        mock_cabinet_service,
    ):
        await list_entries(session=mock_session, user_id=_USER_ID, search="apap")

        call_kwargs = mock_cabinet_service.list_entries.call_args.kwargs
        assert call_kwargs["search"] == "apap"
        assert "category" in call_kwargs
        assert "min_package_count" in call_kwargs

    async def test_no_q_forwards_none(
        self,
        mock_session: AsyncMock,
        mock_users_service,
        mock_cabinet_service,
    ):
        await list_entries(session=mock_session, user_id=_USER_ID)

        call_kwargs = mock_cabinet_service.list_entries.call_args.kwargs
        assert call_kwargs["search"] is None
        assert call_kwargs["category"] is None

    async def test_status_and_order_forwarded(
        self,
        mock_session: AsyncMock,
        mock_users_service,
        mock_cabinet_service,
    ):
        await list_entries(
            session=mock_session,
            user_id=_USER_ID,
            status="expiring",
            order="desc",
            page=2,
            page_size=50,
            category="important",
        )

        call_kwargs = mock_cabinet_service.list_entries.call_args.kwargs
        assert call_kwargs["status"] == "expiring"
        assert call_kwargs["order"] == "desc"
        assert call_kwargs["page"] == 2
        assert call_kwargs["page_size"] == 50
        assert call_kwargs["category"] == "important"

    async def test_category_none_forwarded_by_default(
        self,
        mock_session: AsyncMock,
        mock_users_service,
        mock_cabinet_service,
    ):
        await list_entries(session=mock_session, user_id=_USER_ID)

        call_kwargs = mock_cabinet_service.list_entries.call_args.kwargs
        assert call_kwargs["category"] is None


class TestFacadeSetEntryImportance:
    @pytest.fixture
    def mock_cabinet_service_importance(self, mocker: MockerFixture):
        svc = mocker.patch("app.api.v1.cabinet.facade.cabinet_service", autospec=True)
        svc.set_entry_importance = AsyncMock(return_value=None)
        return svc

    async def test_importance_and_thresholds_forwarded_to_service(
        self,
        mock_session: AsyncMock,
        mock_users_service,
        mock_cabinet_service_importance,
    ):
        await set_entry_importance(
            session=mock_session,
            user_id=_USER_ID,
            entry_id=_ENTRY_ID,
            is_important=True,
        )

        call_kwargs = (
            mock_cabinet_service_importance.set_entry_importance.call_args.kwargs
        )
        assert call_kwargs["user_id"] == _USER_ID
        assert call_kwargs["entry_id"] == _ENTRY_ID
        assert call_kwargs["is_important"] is True
        assert "expiry_threshold_days" in call_kwargs
        assert "min_package_count" in call_kwargs


class TestFacadeSetEntryQuantity:
    @pytest.fixture
    def mock_cabinet_service_quantity(self, mocker: MockerFixture):
        svc = mocker.patch("app.api.v1.cabinet.facade.cabinet_service", autospec=True)
        svc.set_entry_quantity = AsyncMock(return_value=None)
        return svc

    async def test_quantity_and_thresholds_forwarded_to_service(
        self,
        mock_session: AsyncMock,
        mock_users_service,
        mock_cabinet_service_quantity,
    ):
        await set_entry_quantity(
            session=mock_session,
            user_id=_USER_ID,
            entry_id=_ENTRY_ID,
            package_count=0,
            partial_tablet_count=None,
        )

        call_kwargs = mock_cabinet_service_quantity.set_entry_quantity.call_args.kwargs
        assert call_kwargs["user_id"] == _USER_ID
        assert call_kwargs["entry_id"] == _ENTRY_ID
        assert call_kwargs["package_count"] == 0
        assert call_kwargs["partial_tablet_count"] is None
        assert "expiry_threshold_days" in call_kwargs
        assert "min_package_count" in call_kwargs
