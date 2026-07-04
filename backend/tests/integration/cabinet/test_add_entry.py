"""Integration tests for the POST /cabinet/entries write path."""

from collections.abc import Awaitable, Callable
from datetime import date, timedelta

import pytest
from httpx import AsyncClient

from app.api.v1.auth.types import CurrentUser
from app.api.v1.cabinet.models import CabinetEntry
from app.api.v1.medicines.models import MedicationRegistry
from app.api.v1.users.models import User


@pytest.mark.asyncio
async def test_add_entry_merges_on_duplicate_dedup_key(
    authed_db_client: tuple[AsyncClient, Callable[[CurrentUser], None]],
    seed_user: Callable[..., Awaitable[tuple[User, CurrentUser]]],
    seed_registry: Callable[..., Awaitable[MedicationRegistry]],
    seed_entry: Callable[..., Awaitable[CabinetEntry]],
    today: date,
) -> None:
    """POST to the same (medication_registry_id, expiry_date) merges into one entry (FR-010)."""
    client, act_as = authed_db_client
    expiry = today + timedelta(days=60)

    user, current_user = await seed_user()
    registry = await seed_registry()

    initial = await seed_entry(
        user=user, registry=registry, package_count=2, expiry_date=expiry
    )

    act_as(current_user)
    response = await client.post(
        "/api/v1/cabinet/entries",
        json={
            "medication_registry_id": str(registry.id),
            "package_count": 3,
            "expiry_date": expiry.isoformat(),
        },
    )

    assert response.status_code == 201
    body = response.json()
    assert body["merged"] is True
    assert body["entry"]["id"] == str(initial.id)
    assert body["entry"]["package_count"] == 5  # 2 + 3

    # Only one entry in the cabinet — no duplicate row created
    list_response = await client.get("/api/v1/cabinet/entries")
    assert list_response.json()["total"] == 1
