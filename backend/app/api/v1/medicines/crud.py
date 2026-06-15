"""Medicines database operations."""

import logging
from collections.abc import Sequence

from sqlalchemy import Row
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.medicines import queries
from app.utilities.errors import MedicineSearchError

logger = logging.getLogger("app.medicines.crud")


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
            queries.SEARCH_PRODUCTS, {"tsquery": tsquery, "limit": limit}
        )
    except SQLAlchemyError as exc:
        logger.error("Medicines registry search failed: %s", exc, exc_info=True)
        raise MedicineSearchError() from exc
    return result.all()


async def list_variants(
    session: AsyncSession,
    name: str,
    strength: str | None,
    pharmaceutical_form: str | None,
) -> Sequence[Row]:
    """Fetch all pack-size variants for a given product key.

    The product key is matched case-insensitively and NULL-safely so that
    selecting a product from the Phase 2 results always returns its full
    set of variants regardless of casing inconsistencies in the source
    registry.

    Args:
        session: Active async database session.
        name: Product name (case-insensitive match).
        strength: Dosage strength, or None to match rows where strength is NULL.
        pharmaceutical_form: Pharmaceutical form, or None to match NULL rows.

    Returns:
        Rows of (id, name, strength, pharmaceutical_form, capacity, capacity_unit,
        is_tablet_based, active_ingredient, route_of_administration) ordered by
        ``capacity`` ascending (NULLs last).

    Raises:
        MedicineSearchError: If the database query fails.
    """
    try:
        result = await session.execute(
            queries.LIST_VARIANTS,
            {
                "name": name,
                "strength": strength,
                "pharmaceutical_form": pharmaceutical_form,
            },
        )
    except SQLAlchemyError as exc:
        logger.error("Medicines variants lookup failed: %s", exc, exc_info=True)
        raise MedicineSearchError("Failed to fetch medicine variants.") from exc
    return result.all()
