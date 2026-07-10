"""GET /cabinet/summary — five dashboard counts, parity with GET /cabinet/entries.

Each test seeds a known mix and asserts exact counts, including expiry-threshold
boundaries (exactly-today, exactly-threshold-day) and the below-minimum
important-entry case. Parity tests confirm total == valid+expiring+expired and
that each status count matches the corresponding entries-list total.
"""

from collections.abc import Awaitable, Callable
from datetime import date, timedelta

import pytest
from httpx import AsyncClient

from app.api.v1.auth.types import CurrentUser
from app.api.v1.cabinet.models import CabinetEntry
from app.api.v1.medicines.models import MedicationRegistry
from app.api.v1.users.models import User, UserPreferences


@pytest.mark.asyncio
async def test_summary_empty_cabinet_returns_all_zeros(
    authed_db_client: tuple[AsyncClient, Callable[[CurrentUser], None]],
    seed_user: Callable[..., Awaitable[tuple[User, CurrentUser]]],
) -> None:
    """An empty cabinet returns five zero counts."""
    client, act_as = authed_db_client

    _, current_user = await seed_user()

    act_as(current_user)
    response = await client.get("/api/v1/cabinet/summary")

    assert response.status_code == 200
    assert response.json() == {
        "total": 0,
        "valid": 0,
        "expiring": 0,
        "expired": 0,
        "out_of_stock": 0,
    }


@pytest.mark.asyncio
async def test_summary_counts_expiry_threshold_boundaries(
    authed_db_client: tuple[AsyncClient, Callable[[CurrentUser], None]],
    seed_user: Callable[..., Awaitable[tuple[User, CurrentUser]]],
    seed_registry: Callable[..., Awaitable[MedicationRegistry]],
    seed_entry: Callable[..., Awaitable[CabinetEntry]],
    today: date,
) -> None:
    """Assert expiry-status boundaries at the default 30-day threshold.

    expiry_date == today is expiring; expiry_date == today+threshold is
    expiring; expiry_date == today+threshold+1 is valid; expiry_date == today-1
    is expired.
    """
    client, act_as = authed_db_client

    user, current_user = await seed_user()
    registry = await seed_registry()

    await seed_entry(
        user=user, registry=registry, expiry_date=today - timedelta(days=1)
    )
    await seed_entry(user=user, registry=registry, expiry_date=today)
    await seed_entry(
        user=user, registry=registry, expiry_date=today + timedelta(days=30)
    )
    await seed_entry(
        user=user, registry=registry, expiry_date=today + timedelta(days=31)
    )

    act_as(current_user)
    response = await client.get("/api/v1/cabinet/summary")

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 4
    assert body["expired"] == 1
    assert body["expiring"] == 2
    assert body["valid"] == 1
    assert body["out_of_stock"] == 0


@pytest.mark.asyncio
async def test_summary_out_of_stock_counts_below_minimum_important_entries(
    authed_db_client: tuple[AsyncClient, Callable[[CurrentUser], None]],
    seed_user: Callable[..., Awaitable[tuple[User, CurrentUser]]],
    seed_user_preferences: Callable[..., Awaitable[UserPreferences]],
    seed_registry: Callable[..., Awaitable[MedicationRegistry]],
    seed_entry: Callable[..., Awaitable[CabinetEntry]],
    today: date,
) -> None:
    """out_of_stock counts only important entries with package_count < min_package_count."""
    client, act_as = authed_db_client
    min_count = 3

    user, current_user = await seed_user()
    await seed_user_preferences(user=user, min_package_count=min_count)
    registry = await seed_registry()

    await seed_entry(
        user=user,
        registry=registry,
        is_important=True,
        package_count=1,
        expiry_date=today + timedelta(days=60),
    )
    await seed_entry(
        user=user,
        registry=registry,
        is_important=True,
        package_count=5,
        expiry_date=today + timedelta(days=61),
    )
    await seed_entry(
        user=user,
        registry=registry,
        is_important=False,
        package_count=1,
        expiry_date=today + timedelta(days=62),
    )

    act_as(current_user)
    response = await client.get("/api/v1/cabinet/summary")

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 3
    assert body["out_of_stock"] == 1


@pytest.mark.asyncio
async def test_summary_parity_total_equals_status_sum(
    authed_db_client: tuple[AsyncClient, Callable[[CurrentUser], None]],
    seed_user: Callable[..., Awaitable[tuple[User, CurrentUser]]],
    seed_registry: Callable[..., Awaitable[MedicationRegistry]],
    seed_entry: Callable[..., Awaitable[CabinetEntry]],
    today: date,
) -> None:
    """Total == valid + expiring + expired for a mixed seeded cabinet."""
    client, act_as = authed_db_client

    user, current_user = await seed_user()
    registry = await seed_registry()

    await seed_entry(
        user=user, registry=registry, expiry_date=today - timedelta(days=5)
    )
    await seed_entry(
        user=user, registry=registry, expiry_date=today + timedelta(days=10)
    )
    await seed_entry(
        user=user, registry=registry, expiry_date=today + timedelta(days=60)
    )
    await seed_entry(
        user=user, registry=registry, expiry_date=today + timedelta(days=90)
    )

    act_as(current_user)
    response = await client.get("/api/v1/cabinet/summary")

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == body["valid"] + body["expiring"] + body["expired"]


@pytest.mark.asyncio
async def test_summary_status_counts_match_entries_list_totals(
    authed_db_client: tuple[AsyncClient, Callable[[CurrentUser], None]],
    seed_user: Callable[..., Awaitable[tuple[User, CurrentUser]]],
    seed_registry: Callable[..., Awaitable[MedicationRegistry]],
    seed_entry: Callable[..., Awaitable[CabinetEntry]],
    today: date,
) -> None:
    """Each status count in the summary matches GET /cabinet/entries?status=<s>'s total."""
    client, act_as = authed_db_client

    user, current_user = await seed_user()
    registry = await seed_registry()

    await seed_entry(
        user=user, registry=registry, expiry_date=today - timedelta(days=5)
    )
    await seed_entry(
        user=user, registry=registry, expiry_date=today + timedelta(days=10)
    )
    await seed_entry(
        user=user, registry=registry, expiry_date=today + timedelta(days=11)
    )
    await seed_entry(
        user=user, registry=registry, expiry_date=today + timedelta(days=60)
    )

    act_as(current_user)
    summary_response = await client.get("/api/v1/cabinet/summary")
    assert summary_response.status_code == 200
    summary = summary_response.json()

    for status_value in ("valid", "expiring", "expired"):
        list_response = await client.get(
            "/api/v1/cabinet/entries", params={"status": status_value}
        )
        assert list_response.status_code == 200
        assert summary[status_value] == list_response.json()["total"]
