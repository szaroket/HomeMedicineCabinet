"""Medicines business logic."""

import logging

from sqlmodel.ext.asyncio.session import AsyncSession

from app.api.v1.medicines import crud
from app.api.v1.medicines.schemas import ProductOut, VariantOut
from app.utilities.common import build_tsquery

logger = logging.getLogger("app.medicines.service")

_DEFAULT_LIMIT = 20
_MAX_LIMIT = 50


async def search_products(
    session: AsyncSession,
    query: str,
    limit: int = _DEFAULT_LIMIT,
) -> list[ProductOut]:
    """Search the registry for distinct products matching a query.

    Args:
        session (AsyncSession): Active async database session.
        query (str): Raw user search string (name or active ingredient).
        limit (int): Maximum number of products to return; clamped to [1, 50].

    Returns:
        list[ProductOut]: A list of matching products, or an empty list when the query has fewer
        than two effective characters.
    """
    tsquery = build_tsquery(query)
    if tsquery is None:
        logger.debug("Product search skipped: query too short")
        return []
    limit = max(1, min(limit, _MAX_LIMIT))
    rows = await crud.search_products(session, tsquery, limit)
    products = [ProductOut.model_validate(row) for row in rows]
    logger.info("Product search returned %d result(s)", len(products))
    return products


async def list_variants(
    session: AsyncSession,
    name: str,
    strength: str | None,
    pharmaceutical_form: str | None,
) -> list[VariantOut]:
    """Return all pack-size variants for a given product.

    Args:
        session (AsyncSession): Active async database session.
        name (str): Product name as returned by the products endpoint.
        strength (str | None): Dosage strength, or None to match products with no strength recorded.
        pharmaceutical_form (str | None): Pharmaceutical form, or None to match products with no form.

    Returns:
        list[VariantOut]: All registry rows that share the same case-folded product key, ordered
        by capacity ascending.
    """
    rows = await crud.list_variants(session, name, strength, pharmaceutical_form)
    variants = [VariantOut.model_validate(row) for row in rows]
    logger.info("Listed %d variant(s) for product %r", len(variants), name)
    return variants
