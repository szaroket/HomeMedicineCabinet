"""Medicines endpoints: product search, pack-size variants."""

from typing import Annotated

import logging

from fastapi import APIRouter, Depends, HTTPException, Query, Security, status
from sqlmodel.ext.asyncio.session import AsyncSession

from app.api.v1.medicines import service as medicines_service
from app.api.v1.medicines.schemas import ProductOut, VariantOut
from app.core.jwt_security import get_current_user
from app.db.connector import get_session
from app.utilities.errors import MedicineSearchError
from app.utilities.types import NonEmptyStr

logger = logging.getLogger("app.medicines.router")

router = APIRouter(
    prefix="/medicines", tags=["medicines"], dependencies=[Security(get_current_user)]
)


@router.get("/products", response_model=list[ProductOut])
async def search_products(
    search: Annotated[
        NonEmptyStr,
        Query(description="Search term (matches name or active ingredient)."),
    ],
    limit: int = Query(20, ge=1, le=50, description="Maximum number of products."),
    session: AsyncSession = Depends(get_session),
) -> list[ProductOut]:
    """Search the registry for distinct products by name or active ingredient.

    Returns an empty list when the query has fewer than two effective
    characters, so the client can debounce freely without special-casing
    short inputs.
    """
    try:
        return await medicines_service.search_products(session, search, limit)
    except MedicineSearchError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)
        ) from exc
    except Exception as exc:
        logger.exception("Unexpected error in search_products: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred.",
        ) from exc


@router.get("/variants", response_model=list[VariantOut])
async def list_variants(
    name: Annotated[
        NonEmptyStr,
        Query(description="Product name (as returned by /products)."),
    ],
    strength: str | None = Query(
        None, description="Dosage strength; omit to match NULL."
    ),
    form: str | None = Query(
        None, description="Pharmaceutical form; omit to match NULL."
    ),
    session: AsyncSession = Depends(get_session),
) -> list[VariantOut]:
    """Return all pack-size variants for a selected product.

    Pass the ``name``, ``strength``, and ``form`` values exactly as returned
    by ``/products``. Absent ``strength`` or ``form`` matches registry rows
    where those fields are NULL.
    """
    try:
        return await medicines_service.list_variants(session, name, strength, form)
    except MedicineSearchError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)
        ) from exc
    except Exception as exc:
        logger.exception("Unexpected error in list_variants: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred.",
        ) from exc
