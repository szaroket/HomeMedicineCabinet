"""Cabinet endpoints."""

import logging
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Security, status
from sqlmodel.ext.asyncio.session import AsyncSession

from app.api.v1.cabinet import facade as cabinet_facade
from app.api.v1.cabinet import service as cabinet_service
from app.api.v1.cabinet.schemas import (
    AddEntryRequest,
    AddEntryResult,
    CabinetEntryOut,
    CabinetListParams,
    CabinetPageOut,
    SetImportantRequest,
    UsageFields,
)
from app.api.v1.auth.types import CurrentUser
from app.core.jwt_security import get_current_user
from app.db.connector import get_session
from app.utilities.errors import (
    CabinetDatabaseError,
    CabinetError,
    CabinetInvariantError,
    EntryNotFoundError,
    InvalidDosageError,
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
    response_model=CabinetPageOut,
)
async def list_entries(
    params: Annotated[CabinetListParams, Query()],
    current_user: CurrentUser = Security(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> CabinetPageOut:
    """Return the authenticated user's cabinet entries, filtered and paginated."""
    try:
        return await cabinet_facade.list_entries(
            session=session,
            user_id=current_user.id,
            status=params.status,
            search=params.search,
            order=params.order,
            page=params.page,
            page_size=params.page_size,
            category=params.category,
            below_minimum=params.below_minimum,
            sufficiency=params.sufficiency,
        )
    except (CabinetDatabaseError, UserDatabaseError) as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=exc.message
        ) from exc
    except CabinetError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=exc.message
        ) from exc
    except Exception as exc:
        logger.exception(
            "Unexpected error when listing entries | params=%s | error=%s",
            params.model_dump(exclude_none=True),
            exc,
        )
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
            is_important=data.is_important,
            usage=data.usage,
        )
    except MedicationNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=e.message
        ) from e
    except (
        InvalidPackageCountError,
        InvalidPartialTabletCountError,
        InvalidDosageError,
    ) as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=e.message
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


@router.patch(
    "/entries/{entry_id}",
    response_model=CabinetEntryOut,
)
async def set_entry_importance(
    entry_id: uuid.UUID,
    data: SetImportantRequest,
    current_user: CurrentUser = Security(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> CabinetEntryOut:
    """Toggle the importance flag on a cabinet entry owned by the current user."""
    try:
        return await cabinet_facade.set_entry_importance(
            session=session,
            user_id=current_user.id,
            entry_id=entry_id,
            is_important=data.is_important,
        )
    except EntryNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=exc.message
        ) from exc
    except (CabinetDatabaseError, UserDatabaseError) as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=exc.message
        ) from exc
    except CabinetError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=exc.message
        ) from exc
    except Exception as exc:
        logger.exception("Unexpected error when toggling entry importance: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred.",
        ) from exc


@router.delete(
    "/entries/{entry_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_entry(
    entry_id: uuid.UUID,
    current_user: CurrentUser = Security(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> None:
    """Delete a cabinet entry owned by the current user."""
    try:
        await cabinet_service.delete_entry(
            session=session,
            user_id=current_user.id,
            entry_id=entry_id,
        )
    except EntryNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=exc.message
        ) from exc
    except (CabinetDatabaseError, UserDatabaseError) as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=exc.message
        ) from exc
    except CabinetError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=exc.message
        ) from exc
    except Exception as exc:
        logger.exception("Unexpected error when deleting entry: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred.",
        ) from exc


@router.patch(
    "/entries/{entry_id}/usage",
    response_model=CabinetEntryOut,
)
async def set_entry_usage(
    entry_id: uuid.UUID,
    data: UsageFields,
    current_user: CurrentUser = Security(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> CabinetEntryOut:
    """Set, update, or clear the usage/dosage schedule on a cabinet entry owned by the current user."""
    try:
        return await cabinet_facade.set_entry_usage(
            session=session,
            user_id=current_user.id,
            entry_id=entry_id,
            usage=data,
        )
    except EntryNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=exc.message
        ) from exc
    except InvalidDosageError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=exc.message
        ) from exc
    except MedicationNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=exc.message
        ) from exc
    except (CabinetDatabaseError, UserDatabaseError) as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=exc.message
        ) from exc
    except CabinetError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=exc.message
        ) from exc
    except Exception as exc:
        logger.exception("Unexpected error when setting entry usage: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred.",
        ) from exc
