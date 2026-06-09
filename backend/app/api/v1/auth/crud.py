"""Auth database operations."""

import logging
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.users.models import User, UserPreferences
from app.utilities.errors import ProvisioningError

logger = logging.getLogger("app.auth.crud")


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


async def provision_user(session: AsyncSession, user_id: UUID, email: str) -> None:
    """Idempotently provision a local user identity and default preferences.

    Args:
        session: Active async database session.
        user_id: Supabase auth user UUID (equals the JWT `sub` claim).
        email: User's email address.

    Raises:
        ProvisioningError: If the database write fails; the session is rolled
            back so no partial local state is committed.
    """
    now = _utcnow()
    try:
        await session.execute(
            insert(User)
            .values(id=user_id, email=email, created_at=now)
            .on_conflict_do_nothing(index_elements=["id"])
        )
        await session.execute(
            insert(UserPreferences)
            .values(user_id=user_id, created_at=now, updated_at=now)
            .on_conflict_do_nothing(index_elements=["user_id"])
        )
        await session.commit()
    except SQLAlchemyError as e:
        await session.rollback()
        logger.error("Failed to provision user %s: %s", user_id, e, exc_info=True)
        raise ProvisioningError() from e
