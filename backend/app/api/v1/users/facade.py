"""Users facade: cross-domain orchestration between router and service.

This is the only layer permitted to call services from other domains.
Routers call the facade; the facade calls this domain's service plus any
foreign domain's service as needed, then returns the result.
"""

import logging
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.cabinet import service as cabinet_service
from app.api.v1.users import service as users_service
from app.db import supabase_auth
from app.db.connector import persist

logger = logging.getLogger("app.users.facade")


async def delete_account(session: AsyncSession, user_id: uuid.UUID) -> None:
    """Permanently delete a user's local data and their Supabase Auth account.

    Deletes local rows (cabinet entries, then user preferences and the users
    row) as a single atomic unit first; only after that commit succeeds does
    it call the Supabase admin delete. If the local delete fails, nothing is
    changed and Supabase is never called. If the Supabase delete fails after
    the local commit, the local data is already gone — the caller must treat
    this as a partial failure (see router mapping to 502).

    Args:
        session (AsyncSession): Active async database session.
        user_id (uuid.UUID): UUID of the authenticated user to delete.

    Raises:
        CabinetDatabaseError: If deleting the user's cabinet entries fails.
        UserDatabaseError: If deleting the user's local rows fails.
        AccountDeletionError: If the Supabase Auth admin delete fails.
    """
    logger.info("Starting account deletion for user %s", user_id)

    async with persist(session):
        await cabinet_service.delete_by_user(session=session, user_id=user_id)
        await users_service.delete_user_rows(session=session, user_id=user_id)

    supabase_auth.delete_user(str(user_id))

    logger.info("Completed account deletion for user %s", user_id)
