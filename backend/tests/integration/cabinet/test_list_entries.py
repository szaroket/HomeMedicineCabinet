"""Risk #1 — populated cabinet returns its rows with the correct response shape.

Proves that a non-empty cabinet is not silently returned as an empty list and
that each item carries the representative fields required by CabinetEntryOut.
"""

from collections.abc import Awaitable, Callable
from datetime import date, timedelta

import pytest
from httpx import AsyncClient

from app.api.v1.auth.types import CurrentUser
from app.api.v1.cabinet.models import CabinetEntry
from app.api.v1.medicines.models import MedicationRegistry
from app.api.v1.users.models import User


@pytest.mark.asyncio
async def test_populated_cabinet_returns_all_seeded_entries(
    authed_db_client: tuple[AsyncClient, Callable[[CurrentUser], None]],
    seed_user: Callable[..., Awaitable[tuple[User, CurrentUser]]],
    seed_registry: Callable[..., Awaitable[MedicationRegistry]],
    seed_entry: Callable[..., Awaitable[CabinetEntry]],
) -> None:
    """Seeded entries come back with correct shape — not a silent-empty 200."""
    client, act_as = authed_db_client

    user, current_user = await seed_user()
    registry = await seed_registry()

    # seed_entry auto-increments expiry_date per call so each entry gets a unique
    # (user_id, medication_registry_id, expiry_date) key and is not merged.
    entry_a = await seed_entry(user, registry)
    entry_b = await seed_entry(user, registry)
    entry_c = await seed_entry(user, registry)
    seeded = {str(e.id): e for e in (entry_a, entry_b, entry_c)}

    act_as(current_user)
    response = await client.get("/api/v1/cabinet/entries")

    assert response.status_code == 200
    data = response.json()
    items = data["items"]

    # Risk #1 core assertion: not a silent-empty response
    assert len(items) > 0, "cabinet returned empty — silent-empty regression"
    assert data["total"] == 3
    assert {item["id"] for item in items} == set(seeded)

    for item in items:
        entry = seeded[item["id"]]
        assert item["package_count"] == entry.package_count
        assert item["expiry_date"] == entry.expiry_date.isoformat()
        assert item["status"] == "valid"
        assert item["is_tablet_based"] is True
        assert item["is_important"] is False


@pytest.mark.asyncio
async def test_each_entry_carries_expected_field_values(
    authed_db_client: tuple[AsyncClient, Callable[[CurrentUser], None]],
    seed_user: Callable[..., Awaitable[tuple[User, CurrentUser]]],
    seed_registry: Callable[..., Awaitable[MedicationRegistry]],
    seed_entry: Callable[..., Awaitable[CabinetEntry]],
    today: date,
) -> None:
    """Representative field values match the seeded data (not defaults or stale values)."""
    client, act_as = authed_db_client

    user, current_user = await seed_user()
    registry = await seed_registry(name="Ibuprofen 400mg tabl.", is_tablet_based=True)

    expiry = today + timedelta(days=60)
    entry = await seed_entry(
        user=user,
        registry=registry,
        package_count=5,
        expiry_date=expiry,
        is_important=True,
    )

    act_as(current_user)
    response = await client.get("/api/v1/cabinet/entries")

    assert response.status_code == 200
    items = response.json()["items"]
    assert len(items) == 1

    item = items[0]
    assert item["id"] == str(entry.id)
    assert item["name"] == "Ibuprofen 400mg tabl."
    assert item["package_count"] == 5
    assert item["expiry_date"] == expiry.isoformat()
    assert item["is_important"] is True
    assert item["is_tablet_based"] is True
    assert item["status"] == "valid"


@pytest.mark.asyncio
async def test_empty_cabinet_returns_zero_total(
    authed_db_client: tuple[AsyncClient, Callable[[CurrentUser], None]],
    seed_user: Callable[..., Awaitable[tuple[User, CurrentUser]]],
) -> None:
    """An empty cabinet returns total=0 and items=[] — no ghost rows from other tests."""
    client, act_as = authed_db_client

    _, current_user = await seed_user()

    act_as(current_user)
    response = await client.get("/api/v1/cabinet/entries")

    assert response.status_code == 200
    data = response.json()
    assert data["items"] == []
    assert data["total"] == 0
