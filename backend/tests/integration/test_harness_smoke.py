"""Smoke tests proving the integration harness end-to-end before risk tests.

Two tests:
1. Seed a user + registry + entry, hit GET /cabinet, assert the seeded entry
   comes back — same-session seam works.
2. Assert an independent test starts with an empty cabinet — rollback isolation
   holds under pytest-randomly.
"""

from collections.abc import Callable

import pytest
from httpx import AsyncClient

from app.api.v1.auth.types import CurrentUser


@pytest.mark.asyncio
async def test_seeded_entry_returned_by_get_cabinet(
    authed_db_client: tuple[AsyncClient, Callable[[CurrentUser], None]],
    seed_user: Callable[..., object],
    seed_registry: Callable[..., object],
    seed_entry: Callable[..., object],
) -> None:
    """Seeded entry is visible to GET /cabinet via the same session."""
    client, act_as = authed_db_client

    user, current_user = await seed_user()  # type: ignore[misc]

    registry = await seed_registry()  # type: ignore[assignment]
    entry = await seed_entry(user=user, registry=registry)  # type: ignore[assignment]

    act_as(current_user)
    response = await client.get("/api/v1/cabinet/entries")

    assert response.status_code == 200
    entry_ids = [item["id"] for item in response.json()["items"]]
    assert str(entry.id) in entry_ids


@pytest.mark.asyncio
async def test_empty_cabinet_after_rollback(
    authed_db_client: tuple[AsyncClient, Callable[[CurrentUser], None]],
    seed_user: Callable[..., object],
) -> None:
    """Cabinet is empty at the start of this test — prior test's rows were rolled back."""
    client, act_as = authed_db_client

    _, current_user = await seed_user()  # type: ignore[misc]

    act_as(current_user)
    response = await client.get("/api/v1/cabinet/entries")

    assert response.status_code == 200
    assert response.json()["items"] == []
