"""Risk #4 — exact id-set membership across filters including intersection.

Each test seeds a known mix, applies a single filter (or a combined filter),
and asserts the returned id-set equals exactly the expected set — never
count-only, never a subset check. Field values of the returned items are also
verified to confirm the filter matched on the right attribute.
"""

from collections.abc import Awaitable, Callable
from datetime import date, timedelta
from decimal import Decimal

import pytest
from httpx import AsyncClient

from app.api.v1.auth.types import CurrentUser
from app.api.v1.cabinet.models import CabinetEntry
from app.api.v1.medicines.models import MedicationRegistry
from app.api.v1.users.models import User, UserPreferences


# ---------------------------------------------------------------------------
# Status filters
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_status_expired_returns_exact_set(
    authed_db_client: tuple[AsyncClient, Callable[[CurrentUser], None]],
    seed_user: Callable[..., Awaitable[tuple[User, CurrentUser]]],
    seed_registry: Callable[..., Awaitable[MedicationRegistry]],
    seed_entry: Callable[..., Awaitable[CabinetEntry]],
    today: date,
) -> None:
    """status=expired returns exactly entries whose expiry_date < today."""
    client, act_as = authed_db_client

    user, current_user = await seed_user()
    registry = await seed_registry()

    entry_expired = await seed_entry(
        user=user, registry=registry, expiry_date=today - timedelta(days=1)
    )
    await seed_entry(
        user=user, registry=registry, expiry_date=today + timedelta(days=10)
    )
    await seed_entry(
        user=user, registry=registry, expiry_date=today + timedelta(days=60)
    )

    act_as(current_user)
    response = await client.get("/api/v1/cabinet/entries", params={"status": "expired"})

    assert response.status_code == 200
    items = response.json()["items"]
    assert {item["id"] for item in items} == {str(entry_expired.id)}
    assert items[0]["status"] == "expired"
    assert items[0]["expiry_date"] == entry_expired.expiry_date.isoformat()


@pytest.mark.asyncio
async def test_status_expiring_returns_exact_set(
    authed_db_client: tuple[AsyncClient, Callable[[CurrentUser], None]],
    seed_user: Callable[..., Awaitable[tuple[User, CurrentUser]]],
    seed_registry: Callable[..., Awaitable[MedicationRegistry]],
    seed_entry: Callable[..., Awaitable[CabinetEntry]],
    today: date,
) -> None:
    """status=expiring returns exactly entries within the default 30-day threshold."""
    client, act_as = authed_db_client

    user, current_user = await seed_user()
    registry = await seed_registry()

    await seed_entry(
        user=user, registry=registry, expiry_date=today - timedelta(days=1)
    )
    entry_expiring = await seed_entry(
        user=user, registry=registry, expiry_date=today + timedelta(days=15)
    )
    await seed_entry(
        user=user, registry=registry, expiry_date=today + timedelta(days=60)
    )

    act_as(current_user)
    response = await client.get(
        "/api/v1/cabinet/entries", params={"status": "expiring"}
    )

    assert response.status_code == 200
    items = response.json()["items"]
    assert {item["id"] for item in items} == {str(entry_expiring.id)}
    assert items[0]["status"] == "expiring"
    assert items[0]["expiry_date"] == entry_expiring.expiry_date.isoformat()


@pytest.mark.asyncio
async def test_status_valid_returns_exact_set(
    authed_db_client: tuple[AsyncClient, Callable[[CurrentUser], None]],
    seed_user: Callable[..., Awaitable[tuple[User, CurrentUser]]],
    seed_registry: Callable[..., Awaitable[MedicationRegistry]],
    seed_entry: Callable[..., Awaitable[CabinetEntry]],
    today: date,
) -> None:
    """status=valid returns exactly entries whose expiry_date > today + 30 days."""
    client, act_as = authed_db_client

    user, current_user = await seed_user()
    registry = await seed_registry()

    await seed_entry(
        user=user, registry=registry, expiry_date=today - timedelta(days=1)
    )
    await seed_entry(
        user=user, registry=registry, expiry_date=today + timedelta(days=15)
    )
    entry_valid = await seed_entry(
        user=user, registry=registry, expiry_date=today + timedelta(days=60)
    )

    act_as(current_user)
    response = await client.get("/api/v1/cabinet/entries", params={"status": "valid"})

    assert response.status_code == 200
    items = response.json()["items"]
    assert {item["id"] for item in items} == {str(entry_valid.id)}
    assert items[0]["status"] == "valid"
    assert items[0]["expiry_date"] == entry_valid.expiry_date.isoformat()


# ---------------------------------------------------------------------------
# Search filter (to_tsquery against the real search_vector column)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_search_matches_seeded_name_via_tsquery(
    authed_db_client: tuple[AsyncClient, Callable[[CurrentUser], None]],
    seed_user: Callable[..., Awaitable[tuple[User, CurrentUser]]],
    seed_registry: Callable[..., Awaitable[MedicationRegistry]],
    seed_entry: Callable[..., Awaitable[CabinetEntry]],
    today: date,
) -> None:
    """Search drives to_tsquery against the real search_vector; prefix match returns only matching entry."""
    client, act_as = authed_db_client

    user, current_user = await seed_user()
    registry_apap = await seed_registry(
        name="Apap 500mg tabl.", active_ingredient="paracetamol"
    )
    registry_ibuprofen = await seed_registry(
        name="Ibuprofen 400mg tabl.", active_ingredient="ibuprofen"
    )

    entry_apap = await seed_entry(
        user=user, registry=registry_apap, expiry_date=today + timedelta(days=60)
    )
    await seed_entry(
        user=user, registry=registry_ibuprofen, expiry_date=today + timedelta(days=61)
    )

    act_as(current_user)
    response = await client.get("/api/v1/cabinet/entries", params={"search": "apap"})

    assert response.status_code == 200
    items = response.json()["items"]
    assert {item["id"] for item in items} == {str(entry_apap.id)}
    assert items[0]["name"] == "Apap 500mg tabl."


# ---------------------------------------------------------------------------
# Category filters
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_category_important_returns_exact_set(
    authed_db_client: tuple[AsyncClient, Callable[[CurrentUser], None]],
    seed_user: Callable[..., Awaitable[tuple[User, CurrentUser]]],
    seed_registry: Callable[..., Awaitable[MedicationRegistry]],
    seed_entry: Callable[..., Awaitable[CabinetEntry]],
    today: date,
) -> None:
    """category=important returns only entries with is_important=True."""
    client, act_as = authed_db_client

    user, current_user = await seed_user()
    registry = await seed_registry()

    entry_important = await seed_entry(
        user=user,
        registry=registry,
        is_important=True,
        expiry_date=today + timedelta(days=60),
    )
    await seed_entry(
        user=user,
        registry=registry,
        is_important=False,
        expiry_date=today + timedelta(days=61),
    )

    act_as(current_user)
    response = await client.get(
        "/api/v1/cabinet/entries", params={"category": "important"}
    )

    assert response.status_code == 200
    items = response.json()["items"]
    assert {item["id"] for item in items} == {str(entry_important.id)}
    assert items[0]["is_important"] is True


@pytest.mark.asyncio
async def test_category_used_returns_exact_set(
    authed_db_client: tuple[AsyncClient, Callable[[CurrentUser], None]],
    seed_user: Callable[..., Awaitable[tuple[User, CurrentUser]]],
    seed_registry: Callable[..., Awaitable[MedicationRegistry]],
    seed_entry: Callable[..., Awaitable[CabinetEntry]],
    today: date,
) -> None:
    """category=used returns only entries with is_used=True."""
    client, act_as = authed_db_client

    user, current_user = await seed_user()
    registry = await seed_registry()

    entry_used = await seed_entry(
        user=user,
        registry=registry,
        is_used=True,
        expiry_date=today + timedelta(days=60),
    )
    await seed_entry(
        user=user,
        registry=registry,
        is_used=False,
        expiry_date=today + timedelta(days=61),
    )

    act_as(current_user)
    response = await client.get("/api/v1/cabinet/entries", params={"category": "used"})

    assert response.status_code == 200
    items = response.json()["items"]
    assert {item["id"] for item in items} == {str(entry_used.id)}
    assert items[0]["is_used"] is True


# ---------------------------------------------------------------------------
# below_minimum filter
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_below_minimum_returns_important_entries_under_threshold(
    authed_db_client: tuple[AsyncClient, Callable[[CurrentUser], None]],
    seed_user: Callable[..., Awaitable[tuple[User, CurrentUser]]],
    seed_user_preferences: Callable[..., Awaitable[UserPreferences]],
    seed_registry: Callable[..., Awaitable[MedicationRegistry]],
    seed_entry: Callable[..., Awaitable[CabinetEntry]],
    today: date,
) -> None:
    """below_minimum=true returns important entries with package_count < user min."""
    client, act_as = authed_db_client
    min_count = 3

    user, current_user = await seed_user()
    await seed_user_preferences(user=user, min_package_count=min_count)
    registry = await seed_registry()

    entry_below = await seed_entry(
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
    response = await client.get(
        "/api/v1/cabinet/entries", params={"below_minimum": "true"}
    )

    assert response.status_code == 200
    items = response.json()["items"]
    assert {item["id"] for item in items} == {str(entry_below.id)}
    assert items[0]["is_important"] is True
    assert items[0]["package_count"] == entry_below.package_count
    assert items[0]["below_minimum"] is True


# ---------------------------------------------------------------------------
# Sufficiency filters
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_sufficiency_sufficient_returns_exact_set(
    authed_db_client: tuple[AsyncClient, Callable[[CurrentUser], None]],
    seed_user: Callable[..., Awaitable[tuple[User, CurrentUser]]],
    seed_registry: Callable[..., Awaitable[MedicationRegistry]],
    seed_entry: Callable[..., Awaitable[CabinetEntry]],
    today: date,
) -> None:
    """sufficiency=sufficient returns used tablet entries whose supply covers the end date.

    Setup: capacity=20, 10 packages → total=200 tablets; rate=2/day → supply=100 days.
    - sufficient entry: end_date=today+50  → supply(100) >= until_end(50) → sufficient
    - insufficient entry: end_date=today+200 → supply(100) < until_end(200) → insufficient
    - unused entry: no verdict
    """
    client, act_as = authed_db_client

    user, current_user = await seed_user()
    registry = await seed_registry(capacity=Decimal("20"), is_tablet_based=True)

    entry_sufficient = await seed_entry(
        user=user,
        registry=registry,
        package_count=10,
        expiry_date=today + timedelta(days=500),
        is_used=True,
        dosage_times=2,
        dosage_period="day",
        dosage_amount=1,
        dosage_start_date=today,
        dosage_end_date=today + timedelta(days=50),
    )
    await seed_entry(
        user=user,
        registry=registry,
        package_count=10,
        expiry_date=today + timedelta(days=501),
        is_used=True,
        dosage_times=2,
        dosage_period="day",
        dosage_amount=1,
        dosage_start_date=today,
        dosage_end_date=today + timedelta(days=200),
    )
    await seed_entry(
        user=user,
        registry=registry,
        expiry_date=today + timedelta(days=502),
        is_used=False,
    )

    act_as(current_user)
    response = await client.get(
        "/api/v1/cabinet/entries", params={"sufficiency": "sufficient"}
    )

    assert response.status_code == 200
    items = response.json()["items"]
    assert {item["id"] for item in items} == {str(entry_sufficient.id)}
    assert items[0]["is_used"] is True
    assert items[0]["is_sufficient"] is True


@pytest.mark.asyncio
async def test_sufficiency_insufficient_returns_exact_set(
    authed_db_client: tuple[AsyncClient, Callable[[CurrentUser], None]],
    seed_user: Callable[..., Awaitable[tuple[User, CurrentUser]]],
    seed_registry: Callable[..., Awaitable[MedicationRegistry]],
    seed_entry: Callable[..., Awaitable[CabinetEntry]],
    today: date,
) -> None:
    """sufficiency=insufficient returns used tablet entries whose supply does not cover the end date."""
    client, act_as = authed_db_client

    user, current_user = await seed_user()
    registry = await seed_registry(capacity=Decimal("20"), is_tablet_based=True)

    await seed_entry(
        user=user,
        registry=registry,
        package_count=10,
        expiry_date=today + timedelta(days=500),
        is_used=True,
        dosage_times=2,
        dosage_period="day",
        dosage_amount=1,
        dosage_start_date=today,
        dosage_end_date=today + timedelta(days=50),
    )
    entry_insufficient = await seed_entry(
        user=user,
        registry=registry,
        package_count=10,
        expiry_date=today + timedelta(days=501),
        is_used=True,
        dosage_times=2,
        dosage_period="day",
        dosage_amount=1,
        dosage_start_date=today,
        dosage_end_date=today + timedelta(days=200),
    )

    act_as(current_user)
    response = await client.get(
        "/api/v1/cabinet/entries", params={"sufficiency": "insufficient"}
    )

    assert response.status_code == 200
    items = response.json()["items"]
    assert {item["id"] for item in items} == {str(entry_insufficient.id)}
    assert items[0]["is_used"] is True
    assert items[0]["is_sufficient"] is False


# ---------------------------------------------------------------------------
# Filter intersection (AND semantics, FR-004)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_filter_intersection_status_and_category_important(
    authed_db_client: tuple[AsyncClient, Callable[[CurrentUser], None]],
    seed_user: Callable[..., Awaitable[tuple[User, CurrentUser]]],
    seed_registry: Callable[..., Awaitable[MedicationRegistry]],
    seed_entry: Callable[..., Awaitable[CabinetEntry]],
    today: date,
) -> None:
    """status=expiring & category=important returns only entries matching BOTH — AND semantics."""
    client, act_as = authed_db_client

    user, current_user = await seed_user()
    registry = await seed_registry()

    # expiring + important → must be in result
    entry_expiring_important = await seed_entry(
        user=user,
        registry=registry,
        is_important=True,
        expiry_date=today + timedelta(days=15),
    )
    # expiring but not important → excluded by category filter
    await seed_entry(
        user=user,
        registry=registry,
        is_important=False,
        expiry_date=today + timedelta(days=16),
    )
    # valid + important → excluded by status filter
    await seed_entry(
        user=user,
        registry=registry,
        is_important=True,
        expiry_date=today + timedelta(days=60),
    )

    act_as(current_user)
    response = await client.get(
        "/api/v1/cabinet/entries",
        params={"status": "expiring", "category": "important"},
    )

    assert response.status_code == 200
    items = response.json()["items"]
    assert {item["id"] for item in items} == {str(entry_expiring_important.id)}
    assert items[0]["status"] == "expiring"
    assert items[0]["is_important"] is True
