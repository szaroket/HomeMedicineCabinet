"""Integration test fixtures: container, session isolation, auth, and seeding factories."""

import os
import subprocess
import uuid
from collections.abc import AsyncIterator, Awaitable, Callable, Iterator
from datetime import date, datetime, timezone
from decimal import Decimal

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import event
from sqlalchemy.ext.asyncio import (
    AsyncConnection,
    AsyncEngine,
    AsyncSession,
    create_async_engine,
)
from sqlalchemy.pool import NullPool
from testcontainers.postgres import PostgresContainer

from app.api.v1.auth.types import CurrentUser
from app.api.v1.cabinet.models import CabinetEntry
from app.api.v1.medicines.models import MedicationRegistry
from app.api.v1.users.models import User, UserPreferences
from app.core.jwt_security import get_current_user
from app.db.connector import get_session
from app.main import app


# ---------------------------------------------------------------------------
# Phase 2 — container + migrated schema
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def pg_container() -> Iterator[PostgresContainer]:
    """Start a disposable Postgres container for the test session."""
    with PostgresContainer("postgres:17-alpine") as container:
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
    try:
        subprocess.run(
            ["uv", "run", "alembic", "upgrade", "head"],
            cwd=".",
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


# ---------------------------------------------------------------------------
# Phase 3 — per-test transaction-rollback isolation
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def db_conn(db_engine: AsyncEngine) -> AsyncIterator[AsyncConnection]:
    """Open a connection and begin an outer transaction that rolls back on teardown."""
    async with db_engine.connect() as conn:
        await conn.begin()
        yield conn
        await conn.rollback()


@pytest_asyncio.fixture
async def db_session(db_conn: AsyncConnection) -> AsyncIterator[AsyncSession]:
    """Per-test AsyncSession joined to the outer transaction via a nested SAVEPOINT.

    The service calls session.commit() through connector.persist(); the nested
    SAVEPOINT + after_transaction_end listener re-opens it so that inner commits
    do not end the outer transaction. The outer transaction rolls back on teardown,
    leaving the DB pristine for the next test.
    """
    session = AsyncSession(db_conn, expire_on_commit=False)

    await db_conn.begin_nested()  # initial SAVEPOINT

    @event.listens_for(session.sync_session, "after_transaction_end")
    def _restart_savepoint(sync_session, transaction):  # noqa: ANN001
        # Re-open the SAVEPOINT after the service's inner commit() ends it,
        # so subsequent flushes in the same test have an active SAVEPOINT.
        # SQLAlchemy 2.0 "join an external transaction" recipe: gate on public
        # connection state instead of the private transaction._parent attribute.
        if db_conn.closed:
            return
        if not db_conn.in_nested_transaction():
            db_conn.sync_connection.begin_nested()

    yield session
    await session.close()


# ---------------------------------------------------------------------------
# Phase 3 — authed_db_client + act_as
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def authed_db_client(
    db_session: AsyncSession,
) -> AsyncIterator[tuple[AsyncClient, Callable[[CurrentUser], None]]]:
    """HTTPX client over the real app, sharing the per-test session.

    Yields a tuple of (client, act_as) where act_as(user) switches the identity
    returned by get_current_user. Defaults to a sentinel that forces callers to
    call act_as() before making requests that need an authenticated user.

    Usage::

        client, act_as = authed_db_client
        act_as(seeded_user)
        response = await client.get("/api/v1/cabinet/entries")
    """
    active_user: CurrentUser | None = None

    async def _override_get_session() -> AsyncIterator[AsyncSession]:
        yield db_session

    def _override_get_current_user() -> CurrentUser:
        if active_user is None:
            raise RuntimeError(
                "act_as() must be called before making authenticated requests"
            )
        return active_user

    def act_as(user: CurrentUser) -> None:
        """Switch the identity returned to the next request."""
        nonlocal active_user
        active_user = user

    app.dependency_overrides[get_session] = _override_get_session
    app.dependency_overrides[get_current_user] = _override_get_current_user

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        yield client, act_as

    app.dependency_overrides.pop(get_session, None)
    app.dependency_overrides.pop(get_current_user, None)


# ---------------------------------------------------------------------------
# Phase 3 — seeding factory fixtures
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def seed_user(
    db_session: AsyncSession,
) -> Callable[..., Awaitable[tuple[User, CurrentUser]]]:
    """Factory: insert a User row and return (User, CurrentUser).

    Args:
        db_session: The per-test session (injected).

    Returns:
        An async callable accepting optional keyword overrides.
    """

    async def _seed(
        email: str | None = None,
        user_id: uuid.UUID | None = None,
    ) -> tuple[User, CurrentUser]:
        resolved_id = user_id or uuid.uuid4()
        resolved_email = email or f"user-{resolved_id}@test.example"
        user = User(id=resolved_id, email=resolved_email)
        db_session.add(user)
        await db_session.flush()
        await db_session.refresh(user)
        current_user = CurrentUser(id=user.id, email=user.email)
        return user, current_user

    return _seed


@pytest_asyncio.fixture
async def seed_user_preferences(
    db_session: AsyncSession,
) -> Callable[..., Awaitable[UserPreferences]]:
    """Factory: insert a UserPreferences row for the given user.

    Args:
        db_session: The per-test session (injected).

    Returns:
        An async callable accepting a User and optional overrides.
    """

    async def _seed(
        user: User,
        expiry_threshold_days: int = 30,
        close_to_finish_threshold_days: int = 7,
        min_package_count: int = 1,
    ) -> UserPreferences:
        prefs = UserPreferences(
            user_id=user.id,
            expiry_threshold_days=expiry_threshold_days,
            close_to_finish_threshold_days=close_to_finish_threshold_days,
            min_package_count=min_package_count,
        )
        db_session.add(prefs)
        await db_session.flush()
        await db_session.refresh(prefs)
        return prefs

    return _seed


@pytest_asyncio.fixture
async def seed_registry(
    db_session: AsyncSession,
) -> Callable[..., Awaitable[MedicationRegistry]]:
    """Factory: insert a MedicationRegistry row (feeds search_vector via Postgres trigger).

    Args:
        db_session: The per-test session (injected).

    Returns:
        An async callable accepting optional keyword overrides.
    """

    async def _seed(
        name: str = "Apap 500mg tabl.",
        active_ingredient: str | None = "paracetamol",
        capacity: Decimal | None = Decimal("20"),
        capacity_unit: str | None = "tabl.",
        is_tablet_based: bool = True,
        registry_id: uuid.UUID | None = None,
        **kwargs: object,
    ) -> MedicationRegistry:
        registry = MedicationRegistry(
            id=registry_id or uuid.uuid4(),
            name=name,
            active_ingredient=active_ingredient,
            capacity=capacity,
            capacity_unit=capacity_unit,
            is_tablet_based=is_tablet_based,
            **kwargs,
        )
        db_session.add(registry)
        await db_session.flush()
        await db_session.refresh(registry)
        return registry

    return _seed


@pytest_asyncio.fixture
async def seed_entry(
    db_session: AsyncSession,
) -> Callable[..., Awaitable[CabinetEntry]]:
    """Factory: insert a CabinetEntry row for the given user and registry.

    Varies expiry_date by default to avoid hitting the unique constraint
    (user_id, medication_registry_id, expiry_date). Callers may override any
    field explicitly.

    Args:
        db_session: The per-test session (injected).

    Returns:
        An async callable accepting a User, MedicationRegistry, and optional overrides.
    """
    _counter = [0]

    async def _seed(
        user: User,
        registry: MedicationRegistry,
        package_count: int = 2,
        expiry_date: date | None = None,
        partial_tablet_count: int | None = None,
        is_important: bool = False,
        is_used: bool = False,
        **kwargs: object,
    ) -> CabinetEntry:
        _counter[0] += 1
        resolved_expiry = expiry_date or date(2026 + _counter[0], 1, 1)
        entry = CabinetEntry(
            user_id=user.id,
            medication_registry_id=registry.id,
            package_count=package_count,
            expiry_date=resolved_expiry,
            partial_tablet_count=partial_tablet_count,
            is_important=is_important,
            is_used=is_used,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
            **kwargs,
        )
        db_session.add(entry)
        await db_session.flush()
        await db_session.refresh(entry)
        return entry

    return _seed


# ---------------------------------------------------------------------------
# Midnight guard
# ---------------------------------------------------------------------------


@pytest.fixture
def today() -> Iterator[date]:
    """Capture today's date once; skip the test if midnight rolled during the run.

    Guards against the one-in-86400 flake where seeding and the HTTP request
    land on different calendar days, making status-filter assertions unreliable.
    Re-run the test when this happens.
    """
    captured = date.today()
    yield captured
    if date.today() != captured:
        pytest.skip("midnight rolled over during test — re-run")
