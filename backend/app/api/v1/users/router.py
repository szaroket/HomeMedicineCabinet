"""Users endpoints."""

import logging

from fastapi import APIRouter, Depends, HTTPException, Security, status
from sqlmodel.ext.asyncio.session import AsyncSession

from app.api.v1.auth.types import CurrentUser
from app.api.v1.users import facade as users_facade
from app.api.v1.users import service as users_service
from app.api.v1.users.schemas import UpdatePreferencesRequest, UserPreferencesOut
from app.core.jwt_security import get_current_user
from app.db.connector import get_session
from app.utilities.errors import (
    AccountDeletionError,
    CabinetDatabaseError,
    UserDatabaseError,
)

logger = logging.getLogger("app.users.router")

router = APIRouter(
    prefix="/users", tags=["users"], dependencies=[Security(get_current_user)]
)


@router.get(
    "/preferences",
    response_model=UserPreferencesOut,
)
async def get_preferences(
    current_user: CurrentUser = Security(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> UserPreferencesOut:
    """Return the authenticated user's preferences, using defaults when no row exists."""
    try:
        return await users_service.get_effective_preferences(
            session=session,
            user_id=current_user.id,
        )
    except UserDatabaseError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=exc.message
        ) from exc
    except Exception as exc:
        logger.exception("Unexpected error when fetching user preferences: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred.",
        ) from exc


@router.delete(
    "/me",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_account(
    current_user: CurrentUser = Security(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> None:
    """Permanently delete the authenticated user's account and all associated data."""
    try:
        await users_facade.delete_account(session=session, user_id=current_user.id)
    except (UserDatabaseError, CabinetDatabaseError) as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=exc.message
        ) from exc
    except AccountDeletionError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY, detail=exc.message
        ) from exc
    except Exception as exc:
        logger.exception("Unexpected error when deleting account: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred.",
        ) from exc


@router.patch(
    "/preferences",
    response_model=UserPreferencesOut,
)
async def patch_preferences(
    data: UpdatePreferencesRequest,
    current_user: CurrentUser = Security(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> UserPreferencesOut:
    """Update the authenticated user's preferences (upsert)."""
    try:
        return await users_service.update_preferences(
            session=session,
            user_id=current_user.id,
            expiry_threshold_days=data.expiry_threshold_days,
            close_to_finish_threshold_days=data.close_to_finish_threshold_days,
            min_package_count=data.min_package_count,
        )
    except UserDatabaseError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=exc.message
        ) from exc
    except Exception as exc:
        logger.exception("Unexpected error when updating user preferences: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred.",
        ) from exc
