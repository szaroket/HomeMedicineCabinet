"""Integration: DELETE /api/v1/users/me exercises the real local cascade.

The router-level unit tests mock the whole facade, so they only prove HTTP
status mapping. These tests run the facade against a migrated Postgres and
prove the cascade behaviour that only Manual Verification covered before:
child-before-parent delete order (no FK violation), that all three user-owned
row-sets disappear, that the shared ``medication_registry`` catalog is left
untouched, and that another user's data is never collateral. The Supabase admin
delete is mocked — this suite is about the local DB, not the auth provider.
"""

from collections.abc import Awaitable, Callable

import pytest
from httpx import AsyncClient
from pytest_mock import MockerFixture
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.auth.types import CurrentUser
from app.api.v1.cabinet.models import CabinetEntry
from app.api.v1.medicines.models import MedicationRegistry
from app.api.v1.users.models import User, UserPreferences


@pytest.mark.asyncio
async def test_delete_account_removes_user_data_and_preserves_registry(
    authed_db_client: tuple[AsyncClient, Callable[[CurrentUser], None]],
    db_session: AsyncSession,
    seed_user: Callable[..., Awaitable[tuple[User, CurrentUser]]],
    seed_user_preferences: Callable[..., Awaitable[UserPreferences]],
    seed_registry: Callable[..., Awaitable[MedicationRegistry]],
    seed_entry: Callable[..., Awaitable[CabinetEntry]],
    mocker: MockerFixture,
) -> None:
    """DELETE /me returns 204, deletes the user's rows, and keeps the registry."""
    client, act_as = authed_db_client
    delete_auth_user = mocker.patch("app.db.supabase_auth.delete_user", autospec=True)

    user, current_user = await seed_user()
    await seed_user_preferences(user)
    registry = await seed_registry()
    await seed_entry(user=user, registry=registry)
    await seed_entry(user=user, registry=registry)

    act_as(current_user)
    response = await client.delete("/api/v1/users/me")

    assert response.status_code == 204

    # All three user-owned row-sets are gone (child-before-parent, no FK error).
    entries = (
        (
            await db_session.execute(
                select(CabinetEntry).where(CabinetEntry.user_id == user.id)
            )
        )
        .scalars()
        .all()
    )
    assert entries == [], "cabinet entries must be deleted"

    prefs = (
        (
            await db_session.execute(
                select(UserPreferences).where(UserPreferences.user_id == user.id)
            )
        )
        .scalars()
        .all()
    )
    assert prefs == [], "user preferences must be deleted"

    users = (
        (await db_session.execute(select(User).where(User.id == user.id)))
        .scalars()
        .all()
    )
    assert users == [], "users row must be deleted"

    # The shared global catalog must be untouched.
    surviving_registry = (
        (
            await db_session.execute(
                select(MedicationRegistry).where(MedicationRegistry.id == registry.id)
            )
        )
        .scalars()
        .all()
    )
    assert len(surviving_registry) == 1, "medication_registry must not be deleted"

    # The Supabase admin delete is called exactly once, only after the local commit.
    delete_auth_user.assert_called_once_with(str(user.id))


@pytest.mark.asyncio
async def test_delete_account_leaves_other_users_data_intact(
    authed_db_client: tuple[AsyncClient, Callable[[CurrentUser], None]],
    db_session: AsyncSession,
    seed_user: Callable[..., Awaitable[tuple[User, CurrentUser]]],
    seed_user_preferences: Callable[..., Awaitable[UserPreferences]],
    seed_registry: Callable[..., Awaitable[MedicationRegistry]],
    seed_entry: Callable[..., Awaitable[CabinetEntry]],
    mocker: MockerFixture,
) -> None:
    """Deleting one account never touches another user's rows (guards over-broad delete)."""
    client, act_as = authed_db_client
    mocker.patch("app.db.supabase_auth.delete_user", autospec=True)

    victim, victim_current = await seed_user()
    await seed_user_preferences(victim)
    registry = await seed_registry()
    await seed_entry(user=victim, registry=registry)

    bystander, _ = await seed_user()
    await seed_user_preferences(bystander)
    await seed_entry(user=bystander, registry=registry)

    act_as(victim_current)
    response = await client.delete("/api/v1/users/me")

    assert response.status_code == 204

    bystander_entries = (
        (
            await db_session.execute(
                select(CabinetEntry).where(CabinetEntry.user_id == bystander.id)
            )
        )
        .scalars()
        .all()
    )
    assert len(bystander_entries) == 1, "other user's cabinet entry must survive"

    bystander_prefs = (
        (
            await db_session.execute(
                select(UserPreferences).where(UserPreferences.user_id == bystander.id)
            )
        )
        .scalars()
        .all()
    )
    assert len(bystander_prefs) == 1, "other user's preferences must survive"

    bystander_row = (
        (await db_session.execute(select(User).where(User.id == bystander.id)))
        .scalars()
        .all()
    )
    assert len(bystander_row) == 1, "other user's row must survive"
