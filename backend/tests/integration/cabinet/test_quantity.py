"""FR-005 residual — quantity PATCH persistence, zero-count CHECK, and recompute.

Proves that PATCH /entries/{id}/quantity persists package_count and
partial_tablet_count, allows package_count=0 (honouring the DB CHECK >= 0),
and returns recomputed status/below_minimum/total_tablets.
"""

import uuid
from collections.abc import Awaitable, Callable
from datetime import date, timedelta
from decimal import Decimal

import pytest
from httpx import AsyncClient

from app.api.v1.auth.types import CurrentUser
from app.api.v1.cabinet.models import CabinetEntry
from app.api.v1.medicines.models import MedicationRegistry
from app.api.v1.users.models import User


@pytest.mark.asyncio
async def test_quantity_patch_persists_counts_and_recomputes_total(
    authed_db_client: tuple[AsyncClient, Callable[[CurrentUser], None]],
    seed_user: Callable[..., Awaitable[tuple[User, CurrentUser]]],
    seed_registry: Callable[..., Awaitable[MedicationRegistry]],
    seed_entry: Callable[..., Awaitable[CabinetEntry]],
    today: date,
) -> None:
    """PATCH persists package_count/partial_tablet_count and recomputes total_tablets.

    Oracle: capacity = 20 tablets/package, new package_count = 3, partial = 10
    → total_tablets = (3-1)*20 + 10 = 50.
    """
    client, act_as = authed_db_client

    user, current_user = await seed_user()
    registry = await seed_registry(capacity=Decimal("20"), is_tablet_based=True)
    entry = await seed_entry(
        user=user,
        registry=registry,
        package_count=1,
        expiry_date=today + timedelta(days=365),
    )

    act_as(current_user)
    response = await client.patch(
        f"/api/v1/cabinet/entries/{entry.id}/quantity",
        json={"package_count": 3, "partial_tablet_count": 10},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["package_count"] == 3
    assert body["partial_tablet_count"] == 10
    assert body["total_tablets"] == 50


@pytest.mark.asyncio
async def test_quantity_patch_allows_zero_package_count(
    authed_db_client: tuple[AsyncClient, Callable[[CurrentUser], None]],
    seed_user: Callable[..., Awaitable[tuple[User, CurrentUser]]],
    seed_registry: Callable[..., Awaitable[MedicationRegistry]],
    seed_entry: Callable[..., Awaitable[CabinetEntry]],
    today: date,
) -> None:
    """PATCH with package_count=0 succeeds and persists at 0 (DB CHECK >= 0 honoured)."""
    client, act_as = authed_db_client

    user, current_user = await seed_user()
    registry = await seed_registry(capacity=Decimal("20"), is_tablet_based=True)
    entry = await seed_entry(
        user=user,
        registry=registry,
        package_count=1,
        is_important=True,
        expiry_date=today + timedelta(days=365),
    )

    act_as(current_user)
    response = await client.patch(
        f"/api/v1/cabinet/entries/{entry.id}/quantity",
        json={"package_count": 0},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["package_count"] == 0
    assert body["partial_tablet_count"] is None
    assert body["below_minimum"] is True


@pytest.mark.asyncio
async def test_quantity_patch_negative_count_returns_422(
    authed_db_client: tuple[AsyncClient, Callable[[CurrentUser], None]],
    seed_user: Callable[..., Awaitable[tuple[User, CurrentUser]]],
    seed_registry: Callable[..., Awaitable[MedicationRegistry]],
    seed_entry: Callable[..., Awaitable[CabinetEntry]],
) -> None:
    """PATCH with a negative package_count is rejected with 422."""
    client, act_as = authed_db_client

    user, current_user = await seed_user()
    registry = await seed_registry()
    entry = await seed_entry(user=user, registry=registry)

    act_as(current_user)
    response = await client.patch(
        f"/api/v1/cabinet/entries/{entry.id}/quantity",
        json={"package_count": -1},
    )

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_quantity_patch_partial_out_of_range_returns_422(
    authed_db_client: tuple[AsyncClient, Callable[[CurrentUser], None]],
    seed_user: Callable[..., Awaitable[tuple[User, CurrentUser]]],
    seed_registry: Callable[..., Awaitable[MedicationRegistry]],
    seed_entry: Callable[..., Awaitable[CabinetEntry]],
) -> None:
    """PATCH with partial_tablet_count >= capacity is rejected with 422."""
    client, act_as = authed_db_client

    user, current_user = await seed_user()
    registry = await seed_registry(capacity=Decimal("20"), is_tablet_based=True)
    entry = await seed_entry(user=user, registry=registry, package_count=2)

    act_as(current_user)
    response = await client.patch(
        f"/api/v1/cabinet/entries/{entry.id}/quantity",
        json={"package_count": 2, "partial_tablet_count": 20},
    )

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_quantity_patch_partial_on_non_tablet_variant_returns_422(
    authed_db_client: tuple[AsyncClient, Callable[[CurrentUser], None]],
    seed_user: Callable[..., Awaitable[tuple[User, CurrentUser]]],
    seed_registry: Callable[..., Awaitable[MedicationRegistry]],
    seed_entry: Callable[..., Awaitable[CabinetEntry]],
) -> None:
    """PATCH supplying partial_tablet_count for a non-tablet variant is rejected with 422."""
    client, act_as = authed_db_client

    user, current_user = await seed_user()
    registry = await seed_registry(is_tablet_based=False)
    entry = await seed_entry(user=user, registry=registry, package_count=2)

    act_as(current_user)
    response = await client.patch(
        f"/api/v1/cabinet/entries/{entry.id}/quantity",
        json={"package_count": 2, "partial_tablet_count": 5},
    )

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_quantity_patch_on_nonexistent_entry_returns_404(
    authed_db_client: tuple[AsyncClient, Callable[[CurrentUser], None]],
    seed_user: Callable[..., Awaitable[tuple[User, CurrentUser]]],
) -> None:
    """PATCH on a non-existent entry id returns 404."""
    client, act_as = authed_db_client
    _, current_user = await seed_user()

    act_as(current_user)
    response = await client.patch(
        f"/api/v1/cabinet/entries/{uuid.uuid4()}/quantity",
        json={"package_count": 1},
    )

    assert response.status_code == 404
