"""Medicines business logic."""

import re

from sqlmodel.ext.asyncio.session import AsyncSession

from app.api.v1.medicines import crud
from app.api.v1.medicines.schemas import ProductOut, VariantOut

_MIN_QUERY_LENGTH = 2
_DEFAULT_LIMIT = 20
_MAX_LIMIT = 50

# Keep unicode word characters (incl. Polish diacritics) and digits; everything
# else — whitespace and tsquery operators (& | ! ( ) : *) — is a token boundary.
# This is what makes the constructed tsquery injection-safe.
_TOKEN_RE = re.compile(r"\w+", re.UNICODE)


def _build_tsquery(query: str) -> str | None:
    """Build a safe prefix ``to_tsquery`` expression from raw user input.

    Splits the query into alphanumeric/word tokens (dropping any tsquery
    operator characters), appends ``:*`` to each for prefix matching, and joins
    them with ``&``. The result is bound as a parameter, never interpolated, so
    user input cannot inject tsquery syntax.

    Args:
        query: Raw user search string.

    Returns:
        A tsquery string (e.g. ``apap:* & forte:*``), or None when the query
        has fewer than two effective characters.
    """
    tokens = _TOKEN_RE.findall(query)
    if sum(len(token) for token in tokens) < _MIN_QUERY_LENGTH:
        return None
    return " & ".join(f"{token}:*" for token in tokens)


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
    tsquery = _build_tsquery(query)
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
