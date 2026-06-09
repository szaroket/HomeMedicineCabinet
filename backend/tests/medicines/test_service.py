"""Unit tests for medicines service layer (business logic, no HTTP or live DB)."""

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from pytest_mock import MockerFixture

from app.api.v1.medicines.schemas import ProductOut
from app.api.v1.medicines.service import _build_tsquery, search_products


def _registry_row(
    name: str = "Apap",
    strength: str | None = "500 mg",
    pharmaceutical_form: str | None = "tablet",
    active_ingredient: str | None = "paracetamol",
) -> SimpleNamespace:
    """Build a stand-in for a CRUD result row exposing the four mapped columns."""
    return SimpleNamespace(
        name=name,
        strength=strength,
        pharmaceutical_form=pharmaceutical_form,
        active_ingredient=active_ingredient,
    )


# ---------------------------------------------------------------------------
# _build_tsquery
# ---------------------------------------------------------------------------


class TestBuildTsquery:
    @pytest.mark.parametrize(
        ("query", "expected"),
        [
            # exactly two effective characters → single prefix token
            ("ap", "ap:*"),
            # multiple words joined with &
            ("apap forte", "apap:* & forte:*"),
            # Polish diacritics are word characters and are preserved
            ("żel", "żel:*"),
            # leading/trailing operator chars are dropped as token boundaries
            ("apap forte 500", "apap:* & forte:* & 500:*"),
            # two single-char tokens still reach the two-character threshold
            ("a b", "a:* & b:*"),
        ],
    )
    def test_builds_prefix_tsquery(self, query, expected):
        assert _build_tsquery(query) == expected

    @pytest.mark.parametrize(
        "query",
        [
            "a",  # one effective character
            "",  # empty
            "   ",  # whitespace only → no tokens
            "&|!():*",  # only tsquery operators → no word tokens
            "a!",  # single word char plus operator → below threshold
        ],
    )
    def test_returns_none_below_threshold(self, query):
        assert _build_tsquery(query) is None

    @pytest.mark.parametrize(
        ("query", "expected"),
        [
            # tsquery operators are stripped, never interpolated → injection-safe
            ("apap & drop", "apap:* & drop:*"),
            ("apap | forte", "apap:* & forte:*"),
            ("apap:* ) | (x", "apap:* & x:*"),
        ],
    )
    def test_strips_tsquery_operators(self, query, expected):
        assert _build_tsquery(query) == expected


# ---------------------------------------------------------------------------
# search_products
# ---------------------------------------------------------------------------


class TestSearchProducts:
    @pytest.mark.asyncio
    async def test_short_query_returns_empty_without_hitting_crud(
        self, mock_session: AsyncMock, mocker: MockerFixture
    ):
        mock_crud = mocker.patch(
            "app.api.v1.medicines.service.crud.search_products",
            autospec=True,
        )

        result = await search_products(mock_session, "a", limit=20)

        assert result == []
        mock_crud.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_maps_rows_to_product_out(
        self, mock_session: AsyncMock, mocker: MockerFixture
    ):
        rows = [
            _registry_row(name="Apap"),
            _registry_row(
                name="Ibuprom",
                strength=None,
                pharmaceutical_form=None,
                active_ingredient=None,
            ),
        ]
        mocker.patch(
            "app.api.v1.medicines.service.crud.search_products",
            autospec=True,
            return_value=rows,
        )

        result = await search_products(mock_session, "apap", limit=20)

        assert result == [
            ProductOut(
                name="Apap",
                strength="500 mg",
                pharmaceutical_form="tablet",
                active_ingredient="paracetamol",
            ),
            ProductOut(
                name="Ibuprom",
                strength=None,
                pharmaceutical_form=None,
                active_ingredient=None,
            ),
        ]

    @pytest.mark.asyncio
    async def test_passes_built_tsquery_to_crud(
        self, mock_session: AsyncMock, mocker: MockerFixture
    ):
        mock_crud = mocker.patch(
            "app.api.v1.medicines.service.crud.search_products",
            autospec=True,
            return_value=[],
        )

        await search_products(mock_session, "apap forte", limit=20)

        mock_crud.assert_awaited_once_with(mock_session, "apap:* & forte:*", 20)

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        ("limit", "expected_limit"),
        [
            (100, 50),  # above max → clamped down to 50
            (0, 1),  # below min → clamped up to 1
            (-5, 1),  # negative → clamped up to 1
            (25, 25),  # within range → unchanged
        ],
    )
    async def test_clamps_limit(
        self, mock_session: AsyncMock, mocker: MockerFixture, limit, expected_limit
    ):
        mock_crud = mocker.patch(
            "app.api.v1.medicines.service.crud.search_products",
            autospec=True,
            return_value=[],
        )

        await search_products(mock_session, "apap", limit=limit)

        mock_crud.assert_awaited_once_with(mock_session, "apap:*", expected_limit)
