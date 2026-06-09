import pytest_asyncio

from app.db.connector import async_session_factory


@pytest_asyncio.fixture
async def db_session():
    async with async_session_factory() as session:
        yield session
        await session.rollback()
