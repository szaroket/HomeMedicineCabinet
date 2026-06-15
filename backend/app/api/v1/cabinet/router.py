"""Cabinet endpoints."""

import logging
from fastapi import APIRouter, Depends, HTTPException, Security, status
from sqlmodel.ext.asyncio.session import AsyncSession

from app.api.v1.cabinet import facade as cabinet_facade
from app.api.v1.cabinet import service as cabinet_service
from app.api.v1.cabinet.schemas import AddEntryRequest, AddEntryResult, CabinetEntryOut
from app.api.v1.auth.types import CurrentUser
from app.core.jwt_security import get_current_user
from app.db.connector import get_session
from app.utilities.errors import (
    CabinetDatabaseError,
    CabinetError,
    CabinetInvariantError,
    InvalidPackageCountError,
    InvalidPartialTabletCountError,
    MedicationNotFoundError,
    UserDatabaseError,
)

logger = logging.getLogger("app.cabinet.router")

router = APIRouter(
    prefix="/cabinet", tags=["cabinet"], dependencies=[Security(get_current_user)]
)


@router.get(
    "/entries",
    response_model=list[CabinetEntryOut],
)
async def list_entries(
    current_user: CurrentUser = Security(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> list[CabinetEntryOut]:
    """Return the authenticated user's cabinet entries with computed status."""
    try:
        return await cabinet_facade.list_entries(
            session=session,
            user_id=current_user.id,
        )
    except (CabinetDatabaseError, UserDatabaseError) as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=e.message
        ) from e
    except CabinetError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=e.message
        ) from e
    except Exception as exc:
        logger.exception("Unexpected error when listing entries: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred.",
        ) from exc


@router.post(
    "/entries",
    response_model=AddEntryResult,
    status_code=status.HTTP_201_CREATED,
)
async def add_entry(
    data: AddEntryRequest,
    current_user: CurrentUser = Security(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> AddEntryResult:
    """Add a medication entry to the current user's cabinet.

    Applies FR-010 dedup/merge when the same (variant, expiry_date) already exists.
    """
    try:
        return await cabinet_service.add_entry(
            session=session,
            user_id=current_user.id,
            medication_registry_id=data.medication_registry_id,
            package_count=data.package_count,
            partial_tablet_count=data.partial_tablet_count,
            expiry_date=data.expiry_date,
        )
    except MedicationNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=e.message
        ) from e
    except (InvalidPackageCountError, InvalidPartialTabletCountError) as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=e.message
        ) from e
    except CabinetInvariantError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=e.message
        ) from e
    except CabinetDatabaseError as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=e.message
        ) from e
    except CabinetError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=e.message
        ) from e
    except Exception as exc:
        logger.exception("Unexpected error when adding new entry: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred.",
        ) from exc
