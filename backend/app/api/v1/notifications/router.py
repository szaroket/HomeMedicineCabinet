"""Notifications endpoints."""

import logging

from fastapi import APIRouter, Depends, HTTPException, Security, status
from sqlmodel.ext.asyncio.session import AsyncSession

from app.api.v1.auth.types import CurrentUser
from app.api.v1.notifications import facade as notifications_facade
from app.api.v1.notifications.schemas import NotificationListOut
from app.core.jwt_security import get_current_user
from app.db.connector import get_session
from app.utilities.errors import (
    CabinetDatabaseError,
    NotificationsDatabaseError,
    UserDatabaseError,
)

logger = logging.getLogger("app.notifications.router")

router = APIRouter(
    prefix="/notifications",
    tags=["notifications"],
    dependencies=[Security(get_current_user)],
)


@router.get(
    "/",
    response_model=NotificationListOut,
)
async def list_notifications(
    current_user: CurrentUser = Security(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> NotificationListOut:
    """Return the authenticated user's active, non-dismissed notifications."""
    try:
        return await notifications_facade.list_notifications(
            session=session,
            user_id=current_user.id,
        )
    except (
        NotificationsDatabaseError,
        UserDatabaseError,
        CabinetDatabaseError,
    ) as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=exc.message
        ) from exc
    except Exception as exc:
        logger.exception("Unexpected error when listing notifications: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred.",
        ) from exc
