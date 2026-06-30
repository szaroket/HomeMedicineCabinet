"""Risk #5 — per-account isolation on reads and writes.

Proves that a user cannot read or write another user's cabinet entries.
Ownership is enforced at the query layer (user_id predicate in find_entry_by_id
and list_entries), not merely by authentication.
"""

from collections.abc import Awaitable, Callable

import pytest
from httpx import AsyncClient

from app.api.v1.auth.types import CurrentUser
from app.api.v1.cabinet.models import CabinetEntry
from app.api.v1.medicines.models import MedicationRegistry
from app.api.v1.users.models import User


@pytest.mark.asyncio
async def test_cross_account_read_returns_no_foreign_entries(
    authed_db_client: tuple[AsyncClient, Callable[[CurrentUser], None]],
    seed_user: Callable[..., Awaitable[tuple[User, CurrentUser]]],
    seed_registry: Callable[..., Awaitable[MedicationRegistry]],
    seed_entry: Callable[..., Awaitable[CabinetEntry]],
) -> None:
    """As user B, GET /cabinet returns none of user A's entries."""
    client, act_as = authed_db_client

    user_a, _ = await seed_user()
    __, current_user_b = await seed_user()
    registry = await seed_registry()

    await seed_entry(user=user_a, registry=registry)
    await seed_entry(user=user_a, registry=registry)

    act_as(current_user_b)
    response = await client.get("/api/v1/cabinet/entries")

    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 0, "user B must not see user A's entries"
    assert data["items"] == []


@pytest.mark.asyncio
async def test_cross_account_importance_patch_returns_404(
    authed_db_client: tuple[AsyncClient, Callable[[CurrentUser], None]],
    seed_user: Callable[..., Awaitable[tuple[User, CurrentUser]]],
    seed_registry: Callable[..., Awaitable[MedicationRegistry]],
    seed_entry: Callable[..., Awaitable[CabinetEntry]],
) -> None:
    """As user B, PATCH /entries/{A_entry_id} returns 404 and leaves A's row unchanged."""
    client, act_as = authed_db_client

    user_a, current_user_a = await seed_user()
    _, current_user_b = await seed_user()
    registry = await seed_registry()
    entry_a = await seed_entry(user=user_a, registry=registry, is_important=False)

    act_as(current_user_b)
    response = await client.patch(
        f"/api/v1/cabinet/entries/{entry_a.id}",
        json={"is_important": True},
    )

    assert response.status_code == 404, "cross-account write must be rejected with 404"

    # Confirm A's row is unchanged — importance is still False.
    act_as(current_user_a)
    list_response = await client.get("/api/v1/cabinet/entries")
    assert list_response.status_code == 200
    items = list_response.json()["items"]
    assert len(items) == 1
    assert items[0]["id"] == str(entry_a.id)
    assert items[0]["is_important"] is False, "victim row must not be mutated"


@pytest.mark.asyncio
async def test_cross_account_usage_patch_returns_404(
    authed_db_client: tuple[AsyncClient, Callable[[CurrentUser], None]],
    seed_user: Callable[..., Awaitable[tuple[User, CurrentUser]]],
    seed_registry: Callable[..., Awaitable[MedicationRegistry]],
    seed_entry: Callable[..., Awaitable[CabinetEntry]],
) -> None:
    """As user B, PATCH /entries/{A_entry_id}/usage returns 404 and leaves A's row unchanged."""
    client, act_as = authed_db_client

    user_a, current_user_a = await seed_user()
    _, current_user_b = await seed_user()
    registry = await seed_registry()
    entry_a = await seed_entry(user=user_a, registry=registry, is_used=False)

    act_as(current_user_b)
    response = await client.patch(
        f"/api/v1/cabinet/entries/{entry_a.id}/usage",
        json={"is_used": False},
    )

    assert response.status_code == 404, (
        "cross-account usage write must be rejected with 404"
    )

    # Confirm A's row is unchanged — is_used is still False.
    act_as(current_user_a)
    list_response = await client.get("/api/v1/cabinet/entries")
    assert list_response.status_code == 200
    items = list_response.json()["items"]
    assert len(items) == 1
    assert items[0]["id"] == str(entry_a.id)
    assert items[0]["is_used"] is False, "victim row must not be mutated"
