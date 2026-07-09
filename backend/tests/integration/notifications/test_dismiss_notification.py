"""POST /api/v1/notifications/dismiss — dismiss lifecycle, GC, and idempotency."""

import uuid
from collections.abc import Awaitable, Callable
from datetime import date

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlmodel import col
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.auth.types import CurrentUser
from app.api.v1.cabinet.models import CabinetEntry
from app.api.v1.medicines.models import MedicationRegistry
from app.api.v1.notifications.models import DismissedNotification
from app.api.v1.users.models import User, UserPreferences


@pytest.mark.asyncio
async def test_dismiss_suppresses_then_gc_then_refires_on_condition_toggle(
    authed_db_client: tuple[AsyncClient, Callable[[CurrentUser], None]],
    db_session: AsyncSession,
    seed_user: Callable[..., Awaitable[tuple[User, CurrentUser]]],
    seed_user_preferences: Callable[..., Awaitable[UserPreferences]],
    seed_registry: Callable[..., Awaitable[MedicationRegistry]],
    seed_entry: Callable[..., Awaitable[CabinetEntry]],
    today: date,
) -> None:
    """Fire -> dismiss -> suppressed -> condition clears (GC) -> re-fires when it returns."""
    client, act_as = authed_db_client

    user, current_user = await seed_user()
    await seed_user_preferences(user, min_package_count=1)
    registry = await seed_registry()
    entry = await seed_entry(
        user=user, registry=registry, package_count=0, is_important=True
    )

    act_as(current_user)

    response = await client.get("/api/v1/notifications/")
    assert response.status_code == 200
    assert len(response.json()["items"]) == 1

    dismiss_response = await client.post(
        "/api/v1/notifications/dismiss",
        json={"cabinet_entry_id": str(entry.id), "trigger_type": "below_minimum"},
    )
    assert dismiss_response.status_code == 204

    response = await client.get("/api/v1/notifications/")
    assert response.status_code == 200
    assert response.json()["items"] == []

    entry.package_count = 5
    db_session.add(entry)
    await db_session.flush()

    response = await client.get("/api/v1/notifications/")
    assert response.status_code == 200
    assert response.json()["items"] == []

    remaining = await db_session.execute(
        select(DismissedNotification).where(
            col(DismissedNotification.cabinet_entry_id) == entry.id
        )
    )
    assert remaining.scalars().all() == []

    entry.package_count = 0
    db_session.add(entry)
    await db_session.flush()

    response = await client.get("/api/v1/notifications/")
    assert response.status_code == 200
    items = response.json()["items"]
    assert len(items) == 1
    assert items[0]["trigger_type"] == "below_minimum"
    assert items[0]["cabinet_entry_id"] == str(entry.id)


@pytest.mark.asyncio
async def test_dismiss_is_idempotent(
    authed_db_client: tuple[AsyncClient, Callable[[CurrentUser], None]],
    db_session: AsyncSession,
    seed_user: Callable[..., Awaitable[tuple[User, CurrentUser]]],
    seed_user_preferences: Callable[..., Awaitable[UserPreferences]],
    seed_registry: Callable[..., Awaitable[MedicationRegistry]],
    seed_entry: Callable[..., Awaitable[CabinetEntry]],
) -> None:
    """Dismissing the same alert twice returns 204 both times and creates one row."""
    client, act_as = authed_db_client

    user, current_user = await seed_user()
    await seed_user_preferences(user, min_package_count=1)
    registry = await seed_registry()
    entry = await seed_entry(
        user=user, registry=registry, package_count=0, is_important=True
    )
    entry_id = entry.id

    act_as(current_user)

    payload = {"cabinet_entry_id": str(entry_id), "trigger_type": "below_minimum"}

    first = await client.post("/api/v1/notifications/dismiss", json=payload)
    assert first.status_code == 204

    second = await client.post("/api/v1/notifications/dismiss", json=payload)
    assert second.status_code == 204

    # The second dismiss hits the unique-constraint race path (IntegrityError ->
    # rollback inside persist()), which expires all ORM objects on the shared
    # session; resync before querying and use the id captured earlier rather
    # than a (now-expired) attribute on `entry`.
    await db_session.rollback()

    rows = await db_session.execute(
        select(DismissedNotification).where(
            col(DismissedNotification.cabinet_entry_id) == entry_id
        )
    )
    assert len(rows.scalars().all()) == 1


@pytest.mark.asyncio
async def test_dismiss_unknown_entry_returns_404_and_inserts_nothing(
    authed_db_client: tuple[AsyncClient, Callable[[CurrentUser], None]],
    db_session: AsyncSession,
    seed_user: Callable[..., Awaitable[tuple[User, CurrentUser]]],
) -> None:
    """Dismissing a non-existent cabinet entry is a foreign-key violation -> 404, no row."""
    client, act_as = authed_db_client

    _, current_user = await seed_user()
    act_as(current_user)

    missing_entry_id = uuid.uuid4()
    response = await client.post(
        "/api/v1/notifications/dismiss",
        json={
            "cabinet_entry_id": str(missing_entry_id),
            "trigger_type": "below_minimum",
        },
    )
    assert response.status_code == 404

    # The failed insert must leave no dismissal behind.
    await db_session.rollback()
    rows = await db_session.execute(
        select(DismissedNotification).where(
            col(DismissedNotification.cabinet_entry_id) == missing_entry_id
        )
    )
    assert rows.scalars().all() == []
