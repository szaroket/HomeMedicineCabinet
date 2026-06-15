from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.sql import text

from app.core.config import settings

# Supabase's transaction pooler (port 6543) does not support asyncpg's
# server-side prepared statements; disable the statement cache there to
# avoid DuplicatePreparedStatementError. The direct connection (5432) is fine.
_connect_args: dict[str, object] = {}
if ":6543" in settings.database_url:
    _connect_args["statement_cache_size"] = 0

engine: AsyncEngine = create_async_engine(
    settings.database_url,
    echo=False,
    pool_pre_ping=True,
    connect_args=_connect_args,
)

async_session_factory: async_sessionmaker[AsyncSession] = async_sessionmaker(
    engine,
    expire_on_commit=False,
)


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    async with async_session_factory() as session:
        yield session


@asynccontextmanager
async def persist(
    session: AsyncSession, *instances: object
) -> AsyncGenerator[None, None]:
    """Flush, refresh, and commit a set of ORM instances, rolling back on error.

    Usage — add instances inside the block; on exit the context manager flushes
    them to obtain server-generated values (e.g. ``id``), refreshes each one,
    and commits. Any exception triggers a rollback and re-raises so the caller
    can translate it into a domain error.

    Args:
        session: Active async database session.
        *instances: ORM model instances to refresh after the flush.

    Yields:
        None — the caller performs ``session.add(...)`` inside the block.
    """
    try:
        yield
        await session.flush()
        for instance in instances:
            await session.refresh(instance)
        await session.commit()
    except Exception:
        await session.rollback()
        raise


async def init_db() -> None:
    async with engine.connect() as conn:
        await conn.execute(text("SELECT 1"))
