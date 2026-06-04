from collections.abc import AsyncGenerator

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


async def init_db() -> None:
    async with engine.connect() as conn:
        await conn.execute(text("SELECT 1"))
