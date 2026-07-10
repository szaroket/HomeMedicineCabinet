"""GET /api/v1/notifications — active-set correctness for seeded mixed inventory."""

from collections.abc import Awaitable, Callable
from datetime import date, timedelta

import pytest
from httpx import AsyncClient

from app.api.v1.auth.types import CurrentUser
from app.api.v1.cabinet.models import CabinetEntry
from app.api.v1.medicines.models import MedicationRegistry
from app.api.v1.users.models import User, UserPreferences


@pytest.mark.asyncio
async def test_mixed_inventory_returns_one_alert_per_trigger(
    authed_db_client: tuple[AsyncClient, Callable[[CurrentUser], None]],
    seed_user: Callable[..., Awaitable[tuple[User, CurrentUser]]],
    seed_user_preferences: Callable[..., Awaitable[UserPreferences]],
    seed_registry: Callable[..., Awaitable[MedicationRegistry]],
    seed_entry: Callable[..., Awaitable[CabinetEntry]],
    today: date,
) -> None:
    """Expiring, below-minimum, and run-out entries each surface exactly once; a healthy entry does not."""
    client, act_as = authed_db_client

    user, current_user = await seed_user()
    await seed_user_preferences(
        user,
        expiry_threshold_days=30,
        close_to_finish_threshold_days=7,
        min_package_count=1,
    )
    registry = await seed_registry()

    expiring_entry = await seed_entry(
        user=user,
        registry=registry,
        expiry_date=today + timedelta(days=10),
    )
    below_min_entry = await seed_entry(
        user=user,
        registry=registry,
        package_count=0,
        is_important=True,
    )
    run_out_entry = await seed_entry(
        user=user,
        registry=registry,
        package_count=1,
        is_used=True,
        dosage_times=1,
        dosage_amount=10,
        dosage_period="day",
        dosage_start_date=today,
        dosage_end_date=today + timedelta(days=10),
    )
    healthy_entry = await seed_entry(
        user=user,
        registry=registry,
        expiry_date=today + timedelta(days=400),
    )

    act_as(current_user)
    response = await client.get("/api/v1/notifications/")

    assert response.status_code == 200
    items = response.json()["items"]

    by_entry_id = {item["cabinet_entry_id"]: item for item in items}

    assert str(expiring_entry.id) in by_entry_id
    assert by_entry_id[str(expiring_entry.id)]["trigger_type"] == "expiry"
    assert by_entry_id[str(expiring_entry.id)]["days_remaining"] == 10

    assert str(below_min_entry.id) in by_entry_id
    assert by_entry_id[str(below_min_entry.id)]["trigger_type"] == "below_minimum"
    assert by_entry_id[str(below_min_entry.id)]["days_remaining"] is None

    assert str(run_out_entry.id) in by_entry_id
    assert by_entry_id[str(run_out_entry.id)]["trigger_type"] == "run_out"
    assert by_entry_id[str(run_out_entry.id)]["days_remaining"] == 2

    assert str(healthy_entry.id) not in by_entry_id
    assert len(items) == 3


@pytest.mark.asyncio
async def test_empty_cabinet_returns_no_notifications(
    authed_db_client: tuple[AsyncClient, Callable[[CurrentUser], None]],
    seed_user: Callable[..., Awaitable[tuple[User, CurrentUser]]],
) -> None:
    """A user with no cabinet entries gets an empty notifications list."""
    client, act_as = authed_db_client

    _, current_user = await seed_user()

    act_as(current_user)
    response = await client.get("/api/v1/notifications/")

    assert response.status_code == 200
    assert response.json()["items"] == []
