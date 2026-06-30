"""Session-scoped Postgres testcontainer and async engine for integration tests."""

import subprocess

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine
from sqlalchemy.pool import NullPool
from testcontainers.postgres import PostgresContainer


@pytest.fixture(scope="session")
def pg_container():
    """Start a disposable Postgres container for the test session."""
    with PostgresContainer("postgres:16-alpine") as container:
        yield container


@pytest.fixture(scope="session")
def pg_url(pg_container: PostgresContainer) -> str:
    """Return an asyncpg-compatible URL for the running container."""
    sync_url: str = pg_container.get_connection_url()
    # testcontainers returns a psycopg2 URL; convert driver to asyncpg
    return sync_url.replace("postgresql+psycopg2://", "postgresql+asyncpg://")


@pytest.fixture(scope="session")
def run_migrations(pg_url: str) -> None:
    """Run alembic upgrade head against the container (subprocess, plain TCP)."""
    # migrations/env.py uses create_async_engine(settings.database_url), so pass asyncpg URL
    subprocess.run(
        ["uv", "run", "alembic", "upgrade", "head"],
        cwd=".",  # must be run from backend/ directory
        env={
            **__import__("os").environ,
            "DATABASE_URL": pg_url,
        },
        check=True,
        capture_output=True,
        text=True,
    )


@pytest_asyncio.fixture(scope="session")
async def db_engine(pg_url: str, run_migrations: None) -> AsyncEngine:
    """Session-scoped async engine bound to the container (NullPool to avoid cross-loop reuse)."""
    engine = create_async_engine(pg_url, poolclass=NullPool)
    yield engine
    await engine.dispose()
