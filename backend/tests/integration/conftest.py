"""Session-scoped Postgres testcontainer and async engine for integration tests."""

import os
import subprocess
from collections.abc import AsyncIterator, Iterator

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine
from sqlalchemy.pool import NullPool
from testcontainers.postgres import PostgresContainer


@pytest.fixture(scope="session")
def pg_container() -> Iterator[PostgresContainer]:
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
    try:
        subprocess.run(
            ["uv", "run", "alembic", "upgrade", "head"],
            cwd=".",  # must be run from backend/ directory
            env={**os.environ, "DATABASE_URL": pg_url},
            check=True,
            capture_output=True,
            text=True,
        )
    except subprocess.CalledProcessError as exc:
        pytest.fail(
            f"alembic upgrade head failed (exit {exc.returncode}):\n"
            f"--- stdout ---\n{exc.stdout}\n--- stderr ---\n{exc.stderr}",
            pytrace=False,
        )


@pytest_asyncio.fixture(scope="session")
async def db_engine(pg_url: str, run_migrations: None) -> AsyncIterator[AsyncEngine]:
    """Session-scoped async engine bound to the container (NullPool to avoid cross-loop reuse)."""
    engine = create_async_engine(pg_url, poolclass=NullPool)
    yield engine
    await engine.dispose()
