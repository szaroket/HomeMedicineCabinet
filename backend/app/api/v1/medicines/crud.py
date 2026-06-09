"""Medicines database operations."""

import logging
from collections.abc import Sequence

from sqlalchemy import Row, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.utilities.errors import MedicineSearchError

logger = logging.getLogger("app.medicines.crud")

# Group case-insensitively on (name, strength, form): the source registry holds
# the same product under inconsistent casing (e.g. "Apap" vs "APAP"), and a
# plain DISTINCT would surface each casing as a separate pick. DISTINCT ON keeps
# one representative row per case-folded group; the trailing ORDER BY columns
# make that representative deterministic. Phase 3's variants lookup must match
# the same case-folded key so selecting a product still fetches every variant.
_SEARCH_PRODUCTS_SQL = text(
    """
    SELECT DISTINCT ON (
            lower(name),
            lower(coalesce(strength, '')),
            lower(coalesce(pharmaceutical_form, ''))
        )
        name, strength, pharmaceutical_form, active_ingredient
    FROM medication_registry
    WHERE search_vector @@ to_tsquery('simple', :tsquery)
    ORDER BY
        lower(name),
        lower(coalesce(strength, '')),
        lower(coalesce(pharmaceutical_form, '')),
        name, strength, pharmaceutical_form
    LIMIT :limit
    """
)


async def search_products(
    session: AsyncSession,
    tsquery: str,
    limit: int,
) -> Sequence[Row]:
    """Run the indexed full-text prefix search for distinct products.

    Queries the ``search_vector`` GIN index (built over name + active
    ingredient with the ``simple`` configuration). The caller is responsible
    for building a safe, parameter-bound ``tsquery`` string.

    Args:
        session: Active async database session.
        tsquery: A pre-built ``to_tsquery('simple', ...)`` expression (e.g.
            ``apap:* & forte:*``); never raw user input.
        limit: Maximum number of distinct products to return.

    Returns:
        One representative row of (name, strength, pharmaceutical_form,
        active_ingredient) per case-folded (name, strength, form) group,
        ordered case-insensitively by name.

    Raises:
        MedicineSearchError: If the database query fails (e.g. the connection
            is unavailable); the underlying SQLAlchemy error is chained.
    """
    try:
        result = await session.execute(
            _SEARCH_PRODUCTS_SQL, {"tsquery": tsquery, "limit": limit}
        )
    except SQLAlchemyError as exc:
        logger.error("Medicines registry search failed: %s", exc, exc_info=True)
        raise MedicineSearchError() from exc
    return result.all()
