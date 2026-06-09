"""Medicines endpoints: product search, pack-size variants."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Security, status
from pydantic import StringConstraints
from sqlmodel.ext.asyncio.session import AsyncSession

from app.api.v1.medicines import service as medicines_service
from app.api.v1.medicines.schemas import ProductOut
from app.core.jwt_security import get_current_user
from app.db.connector import get_session
from app.utilities.errors import MedicineSearchError

# Whitespace is stripped before validation, so a blank/whitespace-only query
# is rejected with 422 (malformed input) rather than silently returning [].
# A real-but-too-short query (e.g. "a") still passes here; the service returns
# [] for fewer than two effective characters.
# Query() must stay INSIDE Annotated (not a default value) or the constraints
# are silently dropped — see lessons.md L-003.
SearchQuery = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1),
    Query(description="Search term (matches name or active ingredient)."),
]

router = APIRouter(
    prefix="/medicines", tags=["medicines"], dependencies=[Security(get_current_user)]
)


@router.get("/products", response_model=list[ProductOut])
async def search_products(
    query: SearchQuery,
    limit: int = Query(20, ge=1, le=50, description="Maximum number of products."),
    session: AsyncSession = Depends(get_session),
) -> list[ProductOut]:
    """Search the registry for distinct products by name or active ingredient.

    Returns an empty list when the query has fewer than two effective
    characters, so the client can debounce freely without special-casing
    short inputs.
    """
    try:
        return await medicines_service.search_products(session, query, limit)
    except MedicineSearchError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)
        ) from exc
