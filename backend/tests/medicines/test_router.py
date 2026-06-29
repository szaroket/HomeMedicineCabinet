"""Integration tests for medicines router (HTTP contract, hermetic — no live DB).

Shared ``client`` / ``authed_client`` fixtures live in ``tests/conftest.py``.
"""

import uuid
from decimal import Decimal

import pytest
from fastapi import status
from httpx import AsyncClient
from pytest_mock import MockerFixture

from app.api.v1.medicines.schemas import ProductOut, VariantOut
from app.utilities.errors import MedicineSearchError


class TestSearchProductsEndpoint:
    PRODUCTS_URL = "/api/v1/medicines/products"

    async def test_missing_token_returns_401_or_403(self, client: AsyncClient):
        # `client` overrides the session only, so the real auth guard runs.
        response = await client.get(self.PRODUCTS_URL, params={"search": "apap"})
        assert response.status_code in (
            status.HTTP_401_UNAUTHORIZED,
            status.HTTP_403_FORBIDDEN,
        )

    async def test_success_returns_200_with_products(
        self, authed_client: AsyncClient, mocker: MockerFixture
    ):
        products = [
            ProductOut(
                name="Apap",
                strength="500 mg",
                pharmaceutical_form="tablet",
                active_ingredient="paracetamol",
            )
        ]
        mock_search = mocker.patch(
            "app.api.v1.medicines.router.medicines_service.search_products",
            autospec=True,
            return_value=products,
        )

        response = await authed_client.get(self.PRODUCTS_URL, params={"search": "apap"})

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data == [
            {
                "name": "Apap",
                "strength": "500 mg",
                "pharmaceutical_form": "tablet",
                "active_ingredient": "paracetamol",
            }
        ]
        mock_search.assert_awaited_once()

    async def test_empty_result_returns_200_with_empty_list(
        self, authed_client: AsyncClient, mocker: MockerFixture
    ):
        mocker.patch(
            "app.api.v1.medicines.router.medicines_service.search_products",
            autospec=True,
            return_value=[],
        )

        response = await authed_client.get(self.PRODUCTS_URL, params={"search": "a"})

        assert response.status_code == status.HTTP_200_OK
        assert response.json() == []

    async def test_default_limit_passed_to_service(
        self, authed_client: AsyncClient, mocker: MockerFixture
    ):
        mock_search = mocker.patch(
            "app.api.v1.medicines.router.medicines_service.search_products",
            autospec=True,
            return_value=[],
        )

        await authed_client.get(self.PRODUCTS_URL, params={"search": "apap"})

        # service called as search_products(session, query, limit)
        assert mock_search.await_args is not None
        assert mock_search.await_args.args[1] == "apap"
        assert mock_search.await_args.args[2] == 20

    async def test_search_error_returns_503(
        self, authed_client: AsyncClient, mocker: MockerFixture
    ):
        mocker.patch(
            "app.api.v1.medicines.router.medicines_service.search_products",
            autospec=True,
            side_effect=MedicineSearchError(),
        )

        response = await authed_client.get(self.PRODUCTS_URL, params={"search": "apap"})

        assert response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE

    async def test_missing_query_returns_422(self, authed_client: AsyncClient):
        response = await authed_client.get(self.PRODUCTS_URL)
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT

    @pytest.mark.parametrize("query", ["", "   "])
    async def test_blank_query_returns_422(self, authed_client: AsyncClient, query):
        response = await authed_client.get(self.PRODUCTS_URL, params={"search": query})
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT

    @pytest.mark.parametrize("limit", [0, 51, -1])
    async def test_out_of_range_limit_returns_422(
        self, authed_client: AsyncClient, mocker: MockerFixture, limit
    ):
        mocker.patch(
            "app.api.v1.medicines.router.medicines_service.search_products",
            autospec=True,
            return_value=[],
        )

        response = await authed_client.get(
            self.PRODUCTS_URL, params={"search": "apap", "limit": limit}
        )

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT

    async def test_unexpected_error_returns_500(
        self, authed_client: AsyncClient, mocker: MockerFixture
    ):
        mocker.patch(
            "app.api.v1.medicines.router.medicines_service.search_products",
            autospec=True,
            side_effect=RuntimeError("boom"),
        )

        response = await authed_client.get(self.PRODUCTS_URL, params={"search": "apap"})

        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR


_FAKE_VARIANT = VariantOut(
    id=uuid.uuid4(),
    name="Apap",
    strength="500 mg",
    pharmaceutical_form="tabletki",
    capacity=Decimal("20"),
    capacity_unit="tabl.",
    is_tablet_based=True,
    active_ingredient="paracetamol",
    route_of_administration="doustnie",
)


class TestListVariantsEndpoint:
    VARIANTS_URL = "/api/v1/medicines/variants"

    async def test_missing_token_returns_401_or_403(self, client: AsyncClient):
        response = await client.get(self.VARIANTS_URL, params={"name": "Apap"})
        assert response.status_code in (
            status.HTTP_401_UNAUTHORIZED,
            status.HTTP_403_FORBIDDEN,
        )

    async def test_success_returns_200_with_variants(
        self, authed_client: AsyncClient, mocker: MockerFixture
    ):
        mocker.patch(
            "app.api.v1.medicines.router.medicines_service.list_variants",
            autospec=True,
            return_value=[_FAKE_VARIANT],
        )

        response = await authed_client.get(
            self.VARIANTS_URL,
            params={"name": "Apap", "strength": "500 mg", "form": "tabletki"},
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert len(data) == 1
        assert data[0]["name"] == "Apap"
        assert data[0]["is_tablet_based"] is True

    async def test_empty_result_returns_200_with_empty_list(
        self, authed_client: AsyncClient, mocker: MockerFixture
    ):
        mocker.patch(
            "app.api.v1.medicines.router.medicines_service.list_variants",
            autospec=True,
            return_value=[],
        )

        response = await authed_client.get(
            self.VARIANTS_URL, params={"name": "Unknown"}
        )

        assert response.status_code == status.HTTP_200_OK
        assert response.json() == []

    async def test_optional_params_default_to_none(
        self, authed_client: AsyncClient, mocker: MockerFixture
    ):
        mock_svc = mocker.patch(
            "app.api.v1.medicines.router.medicines_service.list_variants",
            autospec=True,
            return_value=[],
        )

        await authed_client.get(self.VARIANTS_URL, params={"name": "Apap"})

        # strength and form should be None when not supplied
        assert mock_svc.await_args is not None
        assert mock_svc.await_args.args[2] is None  # strength
        assert mock_svc.await_args.args[3] is None  # form

    async def test_missing_name_returns_422(self, authed_client: AsyncClient):
        response = await authed_client.get(self.VARIANTS_URL)
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT

    @pytest.mark.parametrize("name", ["", "   "])
    async def test_blank_name_returns_422(self, authed_client: AsyncClient, name):
        response = await authed_client.get(self.VARIANTS_URL, params={"name": name})
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT

    async def test_search_error_returns_503(
        self, authed_client: AsyncClient, mocker: MockerFixture
    ):
        mocker.patch(
            "app.api.v1.medicines.router.medicines_service.list_variants",
            autospec=True,
            side_effect=MedicineSearchError(),
        )

        response = await authed_client.get(self.VARIANTS_URL, params={"name": "Apap"})

        assert response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE

    async def test_unexpected_error_returns_500(
        self, authed_client: AsyncClient, mocker: MockerFixture
    ):
        mocker.patch(
            "app.api.v1.medicines.router.medicines_service.list_variants",
            autospec=True,
            side_effect=RuntimeError("boom"),
        )

        response = await authed_client.get(self.VARIANTS_URL, params={"name": "Apap"})

        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
