"""Auth database operations."""

from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.users.models import User, UserPreferences


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


async def provision_user(session: AsyncSession, user_id: UUID, email: str) -> None:
    """Idempotently provision a local user identity and default preferences.

    Args:
        session: Active async database session.
        user_id: Supabase auth user UUID (equals the JWT `sub` claim).
        email: User's email address.
    """
    now = _utcnow()
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
