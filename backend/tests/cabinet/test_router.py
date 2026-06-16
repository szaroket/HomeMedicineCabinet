"""Unit tests for cabinet router HTTP contract (no DB, no real service)."""

from datetime import date
from decimal import Decimal
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from fastapi import status
from httpx import AsyncClient
from pytest_mock import MockerFixture

from app.api.v1.cabinet.schemas import (
    AddEntryOut,
    AddEntryResult,
    CabinetEntryOut,
    CabinetPageOut,
    MergeSummary,
)
from app.utilities.errors import (
    CabinetDatabaseError,
    CabinetError,
    CabinetInvariantError,
    EntryNotFoundError,
    InvalidPartialTabletCountError,
    MedicationNotFoundError,
    UserDatabaseError,
)

_REGISTRY_ID = uuid4()
_ENTRY_ID = uuid4()
_EXPIRY = "2027-06-01"

_VALID_BODY = {
    "medication_registry_id": str(_REGISTRY_ID),
    "package_count": 2,
    "expiry_date": _EXPIRY,
    "partial_tablet_count": 5,
}


def _make_add_entry_out(**overrides) -> AddEntryOut:
    defaults = dict(
        id=_ENTRY_ID,
        name="Apap",
        strength="500 mg",
        pharmaceutical_form="tabletki",
        capacity=Decimal(20),
        capacity_unit="tabl.",
        is_tablet_based=True,
        package_count=2,
        partial_tablet_count=5,
        expiry_date=date(2027, 6, 1),
        total_tablets=25,
    )
    return AddEntryOut(**(defaults | overrides))


def _fresh_result() -> AddEntryResult:
    return AddEntryResult(
        merged=False,
        entry=_make_add_entry_out(),
        merge_summary=None,
    )


def _merged_result() -> AddEntryResult:
    return AddEntryResult(
        merged=True,
        entry=_make_add_entry_out(package_count=3, total_tablets=45),
        merge_summary=MergeSummary(
            previous_package_count=1,
            previous_partial_tablet_count=None,
            previous_total_tablets=20,
            added_total_tablets=25,
            new_total_tablets=45,
        ),
    )


class TestAddEntryAuthGuard:
    @pytest.mark.asyncio
    async def test_missing_token_returns_401(self, client: AsyncClient):
        response = await client.post("/api/v1/cabinet/entries", json=_VALID_BODY)
        assert response.status_code == status.HTTP_401_UNAUTHORIZED


class TestAddEntrySuccess:
    @pytest.mark.asyncio
    async def test_fresh_insert_returns_201_merged_false(
        self, authed_client: AsyncClient, mocker: MockerFixture
    ):
        mocker.patch(
            "app.api.v1.cabinet.router.cabinet_service.add_entry",
            new_callable=AsyncMock,
            return_value=_fresh_result(),
        )

        response = await authed_client.post("/api/v1/cabinet/entries", json=_VALID_BODY)

        assert response.status_code == status.HTTP_201_CREATED
        data = response.json()
        assert data["merged"] is False
        assert data["merge_summary"] is None
        assert data["entry"]["total_tablets"] == 25

    @pytest.mark.asyncio
    async def test_merge_returns_201_merged_true_with_summary(
        self, authed_client: AsyncClient, mocker: MockerFixture
    ):
        mocker.patch(
            "app.api.v1.cabinet.router.cabinet_service.add_entry",
            new_callable=AsyncMock,
            return_value=_merged_result(),
        )

        response = await authed_client.post("/api/v1/cabinet/entries", json=_VALID_BODY)

        assert response.status_code == status.HTTP_201_CREATED
        data = response.json()
        assert data["merged"] is True
        assert data["merge_summary"]["previous_total_tablets"] == 20
        assert data["merge_summary"]["new_total_tablets"] == 45


class TestAddEntryErrorMapping:
    @pytest.mark.asyncio
    async def test_medication_not_found_returns_404(
        self, authed_client: AsyncClient, mocker: MockerFixture
    ):
        mocker.patch(
            "app.api.v1.cabinet.router.cabinet_service.add_entry",
            new_callable=AsyncMock,
            side_effect=MedicationNotFoundError(),
        )

        response = await authed_client.post("/api/v1/cabinet/entries", json=_VALID_BODY)

        assert response.status_code == status.HTTP_404_NOT_FOUND

    @pytest.mark.asyncio
    async def test_invalid_partial_returns_422(
        self, authed_client: AsyncClient, mocker: MockerFixture
    ):
        mocker.patch(
            "app.api.v1.cabinet.router.cabinet_service.add_entry",
            new_callable=AsyncMock,
            side_effect=InvalidPartialTabletCountError(),
        )

        response = await authed_client.post("/api/v1/cabinet/entries", json=_VALID_BODY)

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT

    @pytest.mark.asyncio
    async def test_invariant_error_returns_500(
        self, authed_client: AsyncClient, mocker: MockerFixture
    ):
        mocker.patch(
            "app.api.v1.cabinet.router.cabinet_service.add_entry",
            new_callable=AsyncMock,
            side_effect=CabinetInvariantError(),
        )

        response = await authed_client.post("/api/v1/cabinet/entries", json=_VALID_BODY)

        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR

    @pytest.mark.asyncio
    async def test_database_error_returns_503(
        self, authed_client: AsyncClient, mocker: MockerFixture
    ):
        mocker.patch(
            "app.api.v1.cabinet.router.cabinet_service.add_entry",
            new_callable=AsyncMock,
            side_effect=CabinetDatabaseError(),
        )

        response = await authed_client.post("/api/v1/cabinet/entries", json=_VALID_BODY)

        assert response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE


class TestAddEntryRequestValidation:
    @pytest.mark.asyncio
    async def test_package_count_zero_returns_422(self, authed_client: AsyncClient):
        response = await authed_client.post(
            "/api/v1/cabinet/entries",
            json={**_VALID_BODY, "package_count": 0},
        )
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT

    @pytest.mark.asyncio
    async def test_partial_tablet_count_zero_returns_422(
        self, authed_client: AsyncClient
    ):
        response = await authed_client.post(
            "/api/v1/cabinet/entries",
            json={**_VALID_BODY, "partial_tablet_count": 0},
        )
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT

    @pytest.mark.asyncio
    async def test_missing_expiry_date_returns_422(self, authed_client: AsyncClient):
        body = {k: v for k, v in _VALID_BODY.items() if k != "expiry_date"}
        response = await authed_client.post("/api/v1/cabinet/entries", json=body)
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT

    @pytest.mark.asyncio
    async def test_missing_registry_id_returns_422(self, authed_client: AsyncClient):
        body = {k: v for k, v in _VALID_BODY.items() if k != "medication_registry_id"}
        response = await authed_client.post("/api/v1/cabinet/entries", json=body)
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT


def _make_cabinet_entry_out(**overrides) -> CabinetEntryOut:
    defaults = dict(
        id=_ENTRY_ID,
        name="Apap",
        strength="500 mg",
        pharmaceutical_form="tabletki",
        capacity=Decimal(20),
        capacity_unit="tabl.",
        is_tablet_based=True,
        package_count=2,
        partial_tablet_count=5,
        expiry_date=date(2027, 6, 1),
        total_tablets=25,
        status="valid",
        is_important=False,
        below_minimum=False,
        active_ingredient="Paracetamolum",
        route_of_administration="doustna",
        leaflet_url="https://example.com/leaflet",
        specification_url="https://example.com/spec",
    )
    return CabinetEntryOut(**(defaults | overrides))


class TestListEntriesAuthGuard:
    @pytest.mark.asyncio
    async def test_missing_token_returns_401(self, client: AsyncClient):
        response = await client.get("/api/v1/cabinet/entries")
        assert response.status_code == status.HTTP_401_UNAUTHORIZED


def _make_page_out(entries: list[CabinetEntryOut] | None = None) -> CabinetPageOut:
    items = entries if entries is not None else [_make_cabinet_entry_out()]
    return CabinetPageOut(items=items, total=len(items), page=1, page_size=20)


class TestListEntriesSuccess:
    @pytest.mark.asyncio
    async def test_returns_200_with_entry_list(
        self, authed_client: AsyncClient, mocker: MockerFixture
    ):
        mocker.patch(
            "app.api.v1.cabinet.router.cabinet_facade.list_entries",
            new_callable=AsyncMock,
            return_value=_make_page_out(),
        )

        response = await authed_client.get("/api/v1/cabinet/entries")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["total"] == 1
        assert data["page"] == 1
        assert data["page_size"] == 20
        assert len(data["items"]) == 1
        assert data["items"][0]["name"] == "Apap"
        assert data["items"][0]["status"] == "valid"
        assert data["items"][0]["total_tablets"] == 25

    @pytest.mark.asyncio
    async def test_returns_empty_page_when_no_entries(
        self, authed_client: AsyncClient, mocker: MockerFixture
    ):
        mocker.patch(
            "app.api.v1.cabinet.router.cabinet_facade.list_entries",
            new_callable=AsyncMock,
            return_value=_make_page_out([]),
        )

        response = await authed_client.get("/api/v1/cabinet/entries")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["items"] == []
        assert data["total"] == 0

    @pytest.mark.asyncio
    async def test_query_params_accepted(
        self, authed_client: AsyncClient, mocker: MockerFixture
    ):
        mock_facade = mocker.patch(
            "app.api.v1.cabinet.router.cabinet_facade.list_entries",
            new_callable=AsyncMock,
            return_value=_make_page_out([]),
        )

        response = await authed_client.get(
            "/api/v1/cabinet/entries",
            params={
                "status": "expiring",
                "search": "apap",
                "order": "desc",
                "page": 2,
                "page_size": 50,
            },
        )

        assert response.status_code == status.HTTP_200_OK
        mock_facade.assert_awaited_once()
        call_kwargs = mock_facade.call_args.kwargs
        assert call_kwargs["status"] == "expiring"
        assert call_kwargs["search"] == "apap"
        assert call_kwargs["order"] == "desc"
        assert call_kwargs["page"] == 2
        assert call_kwargs["page_size"] == 50


class TestListEntriesParamValidation:
    @pytest.mark.asyncio
    async def test_invalid_page_size_returns_422(self, authed_client: AsyncClient):
        response = await authed_client.get(
            "/api/v1/cabinet/entries", params={"page_size": 25}
        )
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT

    @pytest.mark.asyncio
    async def test_invalid_status_returns_422(self, authed_client: AsyncClient):
        response = await authed_client.get(
            "/api/v1/cabinet/entries", params={"status": "foo"}
        )
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT

    @pytest.mark.asyncio
    async def test_page_zero_returns_422(self, authed_client: AsyncClient):
        response = await authed_client.get(
            "/api/v1/cabinet/entries", params={"page": 0}
        )
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT

    @pytest.mark.asyncio
    async def test_whitespace_search_returns_422(self, authed_client: AsyncClient):
        response = await authed_client.get(
            "/api/v1/cabinet/entries", params={"search": "   "}
        )
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT

    @pytest.mark.asyncio
    @pytest.mark.parametrize("page_size", [20, 50, 100])
    async def test_valid_page_sizes_accepted(
        self, authed_client: AsyncClient, mocker: MockerFixture, page_size: int
    ):
        mocker.patch(
            "app.api.v1.cabinet.router.cabinet_facade.list_entries",
            new_callable=AsyncMock,
            return_value=_make_page_out([]),
        )
        response = await authed_client.get(
            "/api/v1/cabinet/entries", params={"page_size": page_size}
        )
        assert response.status_code == status.HTTP_200_OK


class TestListEntriesErrorMapping:
    @pytest.mark.asyncio
    async def test_database_error_returns_503(
        self, authed_client: AsyncClient, mocker: MockerFixture
    ):
        mocker.patch(
            "app.api.v1.cabinet.router.cabinet_facade.list_entries",
            new_callable=AsyncMock,
            side_effect=CabinetDatabaseError(),
        )

        response = await authed_client.get("/api/v1/cabinet/entries")

        assert response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE

    @pytest.mark.asyncio
    async def test_user_database_error_returns_503(
        self, authed_client: AsyncClient, mocker: MockerFixture
    ):
        mocker.patch(
            "app.api.v1.cabinet.router.cabinet_facade.list_entries",
            new_callable=AsyncMock,
            side_effect=UserDatabaseError(),
        )

        response = await authed_client.get("/api/v1/cabinet/entries")

        assert response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE

    @pytest.mark.asyncio
    async def test_cabinet_error_returns_400(
        self, authed_client: AsyncClient, mocker: MockerFixture
    ):
        mocker.patch(
            "app.api.v1.cabinet.router.cabinet_facade.list_entries",
            new_callable=AsyncMock,
            side_effect=CabinetError("bad request"),
        )

        response = await authed_client.get("/api/v1/cabinet/entries")

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.json()["detail"] == "bad request"


class TestListEntriesImportanceFields:
    @pytest.mark.asyncio
    async def test_response_includes_is_important_and_below_minimum(
        self, authed_client: AsyncClient, mocker: MockerFixture
    ):
        mocker.patch(
            "app.api.v1.cabinet.router.cabinet_facade.list_entries",
            new_callable=AsyncMock,
            return_value=_make_page_out(
                [_make_cabinet_entry_out(is_important=True, below_minimum=True)]
            ),
        )

        response = await authed_client.get("/api/v1/cabinet/entries")

        assert response.status_code == status.HTTP_200_OK
        item = response.json()["items"][0]
        assert item["is_important"] is True
        assert item["below_minimum"] is True

    @pytest.mark.asyncio
    async def test_category_important_forwarded_to_facade(
        self, authed_client: AsyncClient, mocker: MockerFixture
    ):
        mock_facade = mocker.patch(
            "app.api.v1.cabinet.router.cabinet_facade.list_entries",
            new_callable=AsyncMock,
            return_value=_make_page_out([]),
        )

        response = await authed_client.get(
            "/api/v1/cabinet/entries", params={"category": "important"}
        )

        assert response.status_code == status.HTTP_200_OK
        assert mock_facade.call_args.kwargs["category"] == "important"

    @pytest.mark.asyncio
    async def test_invalid_category_returns_422(self, authed_client: AsyncClient):
        response = await authed_client.get(
            "/api/v1/cabinet/entries", params={"category": "used"}
        )
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT


class TestSetEntryImportanceSuccess:
    @pytest.mark.asyncio
    async def test_toggle_on_returns_200_with_is_important_true(
        self, authed_client: AsyncClient, mocker: MockerFixture
    ):
        mocker.patch(
            "app.api.v1.cabinet.router.cabinet_facade.set_entry_importance",
            new_callable=AsyncMock,
            return_value=_make_cabinet_entry_out(
                is_important=True, below_minimum=False
            ),
        )

        response = await authed_client.patch(
            f"/api/v1/cabinet/entries/{_ENTRY_ID}",
            json={"is_important": True},
        )

        assert response.status_code == status.HTTP_200_OK
        assert response.json()["is_important"] is True

    @pytest.mark.asyncio
    async def test_toggle_off_returns_200_with_is_important_false(
        self, authed_client: AsyncClient, mocker: MockerFixture
    ):
        mocker.patch(
            "app.api.v1.cabinet.router.cabinet_facade.set_entry_importance",
            new_callable=AsyncMock,
            return_value=_make_cabinet_entry_out(
                is_important=False, below_minimum=False
            ),
        )

        response = await authed_client.patch(
            f"/api/v1/cabinet/entries/{_ENTRY_ID}",
            json={"is_important": False},
        )

        assert response.status_code == status.HTTP_200_OK
        assert response.json()["is_important"] is False


class TestSetEntryImportanceErrorMapping:
    @pytest.mark.asyncio
    async def test_entry_not_found_returns_404(
        self, authed_client: AsyncClient, mocker: MockerFixture
    ):
        mocker.patch(
            "app.api.v1.cabinet.router.cabinet_facade.set_entry_importance",
            new_callable=AsyncMock,
            side_effect=EntryNotFoundError(),
        )

        response = await authed_client.patch(
            f"/api/v1/cabinet/entries/{_ENTRY_ID}",
            json={"is_important": True},
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND

    @pytest.mark.asyncio
    async def test_database_error_returns_503(
        self, authed_client: AsyncClient, mocker: MockerFixture
    ):
        mocker.patch(
            "app.api.v1.cabinet.router.cabinet_facade.set_entry_importance",
            new_callable=AsyncMock,
            side_effect=CabinetDatabaseError(),
        )

        response = await authed_client.patch(
            f"/api/v1/cabinet/entries/{_ENTRY_ID}",
            json={"is_important": True},
        )

        assert response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE

    @pytest.mark.asyncio
    async def test_cabinet_error_returns_400(
        self, authed_client: AsyncClient, mocker: MockerFixture
    ):
        mocker.patch(
            "app.api.v1.cabinet.router.cabinet_facade.set_entry_importance",
            new_callable=AsyncMock,
            side_effect=CabinetError("bad request"),
        )

        response = await authed_client.patch(
            f"/api/v1/cabinet/entries/{_ENTRY_ID}",
            json={"is_important": True},
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.json()["detail"] == "bad request"

    @pytest.mark.asyncio
    async def test_missing_token_returns_401(self, client: AsyncClient):
        response = await client.patch(
            f"/api/v1/cabinet/entries/{_ENTRY_ID}",
            json={"is_important": True},
        )
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
