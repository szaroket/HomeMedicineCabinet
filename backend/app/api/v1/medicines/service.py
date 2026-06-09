"""Medicines business logic."""

import re

from sqlmodel.ext.asyncio.session import AsyncSession

from app.api.v1.medicines import crud
from app.api.v1.medicines.schemas import ProductOut

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
    return [
        ProductOut(
            name=row.name,
            strength=row.strength,
            pharmaceutical_form=row.pharmaceutical_form,
            active_ingredient=row.active_ingredient,
        )
        for row in rows
    ]
