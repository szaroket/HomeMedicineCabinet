"""Integration tests for medicines router (HTTP contract, hermetic — no live DB).

Shared ``client`` / ``authed_client`` fixtures live in ``tests/conftest.py``.
"""

import pytest
from fastapi import status
from httpx import AsyncClient
from pytest_mock import MockerFixture

from app.api.v1.medicines.schemas import ProductOut
from app.utilities.errors import MedicineSearchError


class TestSearchProductsEndpoint:
    PRODUCTS_URL = "/api/v1/medicines/products"

    @pytest.mark.asyncio
    async def test_missing_token_returns_401_or_403(self, client: AsyncClient):
        # `client` overrides the session only, so the real auth guard runs.
        response = await client.get(self.PRODUCTS_URL, params={"query": "apap"})
        assert response.status_code in (
            status.HTTP_401_UNAUTHORIZED,
            status.HTTP_403_FORBIDDEN,
        )

    @pytest.mark.asyncio
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

        response = await authed_client.get(self.PRODUCTS_URL, params={"query": "apap"})

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

    @pytest.mark.asyncio
    async def test_empty_result_returns_200_with_empty_list(
        self, authed_client: AsyncClient, mocker: MockerFixture
    ):
        mocker.patch(
            "app.api.v1.medicines.router.medicines_service.search_products",
            autospec=True,
            return_value=[],
        )

        response = await authed_client.get(self.PRODUCTS_URL, params={"query": "a"})

        assert response.status_code == status.HTTP_200_OK
        assert response.json() == []

    @pytest.mark.asyncio
    async def test_default_limit_passed_to_service(
        self, authed_client: AsyncClient, mocker: MockerFixture
    ):
        mock_search = mocker.patch(
            "app.api.v1.medicines.router.medicines_service.search_products",
            autospec=True,
            return_value=[],
        )

        await authed_client.get(self.PRODUCTS_URL, params={"query": "apap"})

        # service called as search_products(session, query, limit)
        assert mock_search.await_args.args[1] == "apap"
        assert mock_search.await_args.args[2] == 20

    @pytest.mark.asyncio
    async def test_search_error_returns_503(
        self, authed_client: AsyncClient, mocker: MockerFixture
    ):
        mocker.patch(
            "app.api.v1.medicines.router.medicines_service.search_products",
            autospec=True,
            side_effect=MedicineSearchError(),
        )

        response = await authed_client.get(self.PRODUCTS_URL, params={"query": "apap"})

        assert response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE

    @pytest.mark.asyncio
    async def test_missing_query_returns_422(self, authed_client: AsyncClient):
        response = await authed_client.get(self.PRODUCTS_URL)
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT

    @pytest.mark.asyncio
    @pytest.mark.parametrize("query", ["", "   "])
    async def test_blank_query_returns_422(self, authed_client: AsyncClient, query):
        response = await authed_client.get(self.PRODUCTS_URL, params={"query": query})
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT

    @pytest.mark.asyncio
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
            self.PRODUCTS_URL, params={"query": "apap", "limit": limit}
        )

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
