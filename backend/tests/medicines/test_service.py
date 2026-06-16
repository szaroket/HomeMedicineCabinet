"""Unit tests for medicines service layer (business logic, no HTTP or live DB)."""

import uuid
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from pytest_mock import MockerFixture

from app.api.v1.medicines.schemas import ProductOut, VariantOut
from app.api.v1.medicines.service import list_variants, search_products
from app.utilities.common import build_tsquery


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


def _variant_row(
    id: uuid.UUID | None = None,
    name: str = "Apap",
    strength: str | None = "500 mg",
    pharmaceutical_form: str | None = "tabletki",
    capacity: Decimal | None = Decimal("20"),
    capacity_unit: str | None = "tabl.",
    is_tablet_based: bool = True,
    active_ingredient: str | None = "paracetamol",
    route_of_administration: str | None = "doustnie",
) -> SimpleNamespace:
    """Build a stand-in for a CRUD result row exposing all VariantOut columns."""
    return SimpleNamespace(
        id=id or uuid.uuid4(),
        name=name,
        strength=strength,
        pharmaceutical_form=pharmaceutical_form,
        capacity=capacity,
        capacity_unit=capacity_unit,
        is_tablet_based=is_tablet_based,
        active_ingredient=active_ingredient,
        route_of_administration=route_of_administration,
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
        assert build_tsquery(query) == expected

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
        assert build_tsquery(query) is None

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
        assert build_tsquery(query) == expected


# ---------------------------------------------------------------------------
# search_products
# ---------------------------------------------------------------------------


class TestSearchProducts:
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


# ---------------------------------------------------------------------------
# list_variants
# ---------------------------------------------------------------------------


class TestListVariants:
    async def test_maps_rows_to_variant_out(
        self, mock_session: AsyncMock, mocker: MockerFixture
    ):
        row = _variant_row()
        mocker.patch(
            "app.api.v1.medicines.service.crud.list_variants",
            autospec=True,
            return_value=[row],
        )

        result = await list_variants(mock_session, "Apap", "500 mg", "tabletki")

        assert len(result) == 1
        assert isinstance(result[0], VariantOut)
        assert result[0].id == row.id
        assert result[0].name == row.name
        assert result[0].is_tablet_based is True

    async def test_passes_args_to_crud(
        self, mock_session: AsyncMock, mocker: MockerFixture
    ):
        mock_crud = mocker.patch(
            "app.api.v1.medicines.service.crud.list_variants",
            autospec=True,
            return_value=[],
        )

        await list_variants(mock_session, "Apap", "500 mg", "tabletki")

        mock_crud.assert_awaited_once_with(mock_session, "Apap", "500 mg", "tabletki")

    async def test_none_strength_and_form_passed_through(
        self, mock_session: AsyncMock, mocker: MockerFixture
    ):
        mock_crud = mocker.patch(
            "app.api.v1.medicines.service.crud.list_variants",
            autospec=True,
            return_value=[],
        )

        await list_variants(mock_session, "Apap", None, None)

        mock_crud.assert_awaited_once_with(mock_session, "Apap", None, None)

    async def test_empty_result_returns_empty_list(
        self, mock_session: AsyncMock, mocker: MockerFixture
    ):
        mocker.patch(
            "app.api.v1.medicines.service.crud.list_variants",
            autospec=True,
            return_value=[],
        )

        result = await list_variants(mock_session, "Unknown", None, None)

        assert result == []
