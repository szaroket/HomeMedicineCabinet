"""Medicines business logic."""

from sqlmodel.ext.asyncio.session import AsyncSession

from app.api.v1.medicines import crud
from app.api.v1.medicines.schemas import ProductOut, VariantOut
from app.utilities.common import build_tsquery

_DEFAULT_LIMIT = 20
_MAX_LIMIT = 50


async def search_products(
    session: AsyncSession,
    query: str,
    limit: int = _DEFAULT_LIMIT,
) -> list[ProductOut]:
    """Search the registry for distinct products matching a query.

    Args:
        session: Active async database session.
        query: Raw user search string (name or active ingredient).
        limit: Maximum number of products to return; clamped to [1, 50].

    Returns:
        A list of matching products, or an empty list when the query has fewer
        than two effective characters.
    """
    tsquery = build_tsquery(query)
    if tsquery is None:
        return []
    limit = max(1, min(limit, _MAX_LIMIT))
    rows = await crud.search_products(session, tsquery, limit)
    return [ProductOut.model_validate(row) for row in rows]


async def list_variants(
    session: AsyncSession,
    name: str,
    strength: str | None,
    pharmaceutical_form: str | None,
) -> list[VariantOut]:
    """Return all pack-size variants for a given product.

    Args:
        session: Active async database session.
        name: Product name as returned by the products endpoint.
        strength: Dosage strength, or None to match products with no strength recorded.
        pharmaceutical_form: Pharmaceutical form, or None to match products with no form.

    Returns:
        All registry rows that share the same case-folded product key, ordered
        by capacity ascending.
    """
    rows = await crud.list_variants(session, name, strength, pharmaceutical_form)
    return [VariantOut.model_validate(row) for row in rows]
