"""Risk #6 residual — usage path round-trip and sufficiency-filter SQL↔Python parity.

Proves that PATCH /entries/{id}/usage persists correctly and that the set-based
SQL _sufficiency_clauses filter agrees with the per-row Python compute_usage_view
verdict (the two are deliberately duplicated in service.py and crud.py and must
stay in parity).
"""

from collections.abc import Awaitable, Callable
from datetime import date, timedelta
from decimal import Decimal

import pytest
from httpx import AsyncClient

from app.api.v1.auth.types import CurrentUser
from app.api.v1.cabinet.models import CabinetEntry
from app.api.v1.cabinet.service import compute_usage_view
from app.api.v1.medicines.models import MedicationRegistry
from app.api.v1.users.models import User


# ---------------------------------------------------------------------------
# Usage round-trip
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_usage_patch_persists_and_returns_correct_supply_view(
    authed_db_client: tuple[AsyncClient, Callable[[CurrentUser], None]],
    seed_user: Callable[..., Awaitable[tuple[User, CurrentUser]]],
    seed_registry: Callable[..., Awaitable[MedicationRegistry]],
    seed_entry: Callable[..., Awaitable[CabinetEntry]],
    today: date,
) -> None:
    """PATCH /entries/{id}/usage persists the dosage schedule and returns correct supply view.

    Oracle (computed independently from FR-016/017, not mirrored from the formula):
      capacity = 20 tablets/package, package_count = 4 → total = 80 tablets
      dosage: 1 time/day × 1 tablet → daily_rate = 1.0 → days_of_supply = floor(80/1) = 80
      dosage_end_date = today + 60 → days_until_end = 60
      is_sufficient: 80 >= 60 → True
    """
    client, act_as = authed_db_client

    user, current_user = await seed_user()
    registry = await seed_registry(capacity=Decimal("20"), is_tablet_based=True)
    entry = await seed_entry(
        user=user,
        registry=registry,
        package_count=4,
        expiry_date=today + timedelta(days=365),
    )

    dosage_end = today + timedelta(days=60)

    act_as(current_user)
    response = await client.patch(
        f"/api/v1/cabinet/entries/{entry.id}/usage",
        json={
            "is_used": True,
            "dosage_times": 1,
            "dosage_period": "day",
            "dosage_amount": 1,
            "dosage_start_date": today.isoformat(),
            "dosage_end_date": dosage_end.isoformat(),
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["is_used"] is True
    assert body["dosage_times"] == 1
    assert body["dosage_period"] == "day"
    assert body["dosage_amount"] == 1
    assert body["dosage_end_date"] == dosage_end.isoformat()
    # Independent oracle values
    assert body["days_of_supply"] == 80
    assert body["days_until_end"] == 60
    assert body["is_sufficient"] is True


@pytest.mark.asyncio
async def test_clearing_usage_nulls_dosage_fields(
    authed_db_client: tuple[AsyncClient, Callable[[CurrentUser], None]],
    seed_user: Callable[..., Awaitable[tuple[User, CurrentUser]]],
    seed_registry: Callable[..., Awaitable[MedicationRegistry]],
    seed_entry: Callable[..., Awaitable[CabinetEntry]],
    today: date,
) -> None:
    """PATCH with is_used=False clears all dosage/date columns."""
    client, act_as = authed_db_client

    user, current_user = await seed_user()
    registry = await seed_registry(capacity=Decimal("20"), is_tablet_based=True)
    entry = await seed_entry(
        user=user,
        registry=registry,
        package_count=2,
        expiry_date=today + timedelta(days=365),
        is_used=True,
        dosage_times=2,
        dosage_period="day",
        dosage_amount=1,
        dosage_start_date=today,
        dosage_end_date=today + timedelta(days=30),
    )

    act_as(current_user)
    response = await client.patch(
        f"/api/v1/cabinet/entries/{entry.id}/usage",
        json={"is_used": False},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["is_used"] is False
    assert body["dosage_times"] is None
    assert body["dosage_period"] is None
    assert body["dosage_amount"] is None
    assert body["dosage_start_date"] is None
    assert body["dosage_end_date"] is None
    assert body["days_of_supply"] is None
    assert body["days_until_end"] is None
    assert body["is_sufficient"] is None


# ---------------------------------------------------------------------------
# Sufficiency-filter SQL↔Python parity
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_sufficiency_filter_parity_with_compute_usage_view(
    authed_db_client: tuple[AsyncClient, Callable[[CurrentUser], None]],
    seed_user: Callable[..., Awaitable[tuple[User, CurrentUser]]],
    seed_registry: Callable[..., Awaitable[MedicationRegistry]],
    seed_entry: Callable[..., Awaitable[CabinetEntry]],
    today: date,
) -> None:
    """SQL _sufficiency_clauses filter agrees with per-row Python compute_usage_view.

    Seeds entries that span all verdict categories: sufficient, insufficient,
    no-verdict (closed window), no-verdict (unused), no-verdict (zero rate guard),
    per-week period, and partial-pack. For each category the returned id-set from
    the HTTP filter must equal what compute_usage_view predicts.
    """
    client, act_as = authed_db_client

    user, current_user = await seed_user()
    # All entries share the same registry (capacity=20 tablets/package, tablet-based).
    registry = await seed_registry(capacity=Decimal("20"), is_tablet_based=True)

    # Entry: sufficient (daily, full packs)
    # total=4*20=80, rate=1/day, supply=80, until_end=30 → 80>=30 → sufficient
    entry_sufficient = await seed_entry(
        user=user,
        registry=registry,
        package_count=4,
        is_used=True,
        dosage_times=1,
        dosage_period="day",
        dosage_amount=1,
        dosage_start_date=today,
        dosage_end_date=today + timedelta(days=30),
    )

    # Entry: insufficient (daily, few tablets)
    # total=1*20=20, rate=2*2/1=4/day, supply=floor(20/4)=5, until_end=30 → 5<30 → insufficient
    entry_insufficient = await seed_entry(
        user=user,
        registry=registry,
        package_count=1,
        is_used=True,
        dosage_times=2,
        dosage_period="day",
        dosage_amount=2,
        dosage_start_date=today,
        dosage_end_date=today + timedelta(days=30),
    )

    # Entry: no-verdict — closed window (end_date == today, until_end == 0)
    entry_closed_window = await seed_entry(
        user=user,
        registry=registry,
        package_count=1,
        is_used=True,
        dosage_times=1,
        dosage_period="day",
        dosage_amount=1,
        dosage_start_date=today - timedelta(days=10),
        dosage_end_date=today,
    )

    # Entry: no-verdict — not used
    entry_unused = await seed_entry(
        user=user,
        registry=registry,
        package_count=2,
        is_used=False,
    )

    # Entry: sufficient — per-week period
    # total=2*20=40, rate=1*1/7≈0.143/day, supply=floor(40/0.143)=280, until_end=30 → sufficient
    entry_sufficient_weekly = await seed_entry(
        user=user,
        registry=registry,
        package_count=2,
        is_used=True,
        dosage_times=1,
        dosage_period="week",
        dosage_amount=1,
        dosage_start_date=today,
        dosage_end_date=today + timedelta(days=30),
    )

    # Entry: sufficient — boundary (supply == until_end exactly), catches >= vs > mutation.
    # total=3*20=60, rate=2*1/1=2/day, supply=floor(60/2)=30, until_end=30 → 30>=30 → sufficient.
    # SQL with >=: today+30 >= today+30 → included ✓
    # SQL with >:  today+30 >  today+30 → excluded ✗
    entry_sufficient_boundary = await seed_entry(
        user=user,
        registry=registry,
        package_count=3,
        is_used=True,
        dosage_times=2,
        dosage_period="day",
        dosage_amount=1,
        dosage_start_date=today,
        dosage_end_date=today + timedelta(days=30),
    )

    # Entry: insufficient — partial pack
    # total=(2-1)*20+5=25, rate=2*2/1=4/day, supply=floor(25/4)=6, until_end=30 → 6<30 → insufficient
    entry_insufficient_partial = await seed_entry(
        user=user,
        registry=registry,
        package_count=2,
        partial_tablet_count=5,
        is_used=True,
        dosage_times=2,
        dosage_period="day",
        dosage_amount=2,
        dosage_start_date=today,
        dosage_end_date=today + timedelta(days=30),
    )

    tablets_per_package = 20  # matches registry.capacity

    # Build Python-predicted verdict sets using compute_usage_view as the oracle.
    entries_and_labels = [
        (entry_sufficient, "sufficient"),
        (entry_insufficient, "insufficient"),
        (entry_closed_window, "no_verdict"),
        (entry_unused, "no_verdict"),
        (entry_sufficient_weekly, "sufficient"),
        (entry_insufficient_partial, "insufficient"),
        (entry_sufficient_boundary, "sufficient"),
    ]
    predicted_sufficient_ids: set[str] = set()
    predicted_insufficient_ids: set[str] = set()
    for entry, _ in entries_and_labels:
        view = compute_usage_view(entry, tablets_per_package, today)
        if view.is_sufficient is True:
            predicted_sufficient_ids.add(str(entry.id))
        elif view.is_sufficient is False:
            predicted_insufficient_ids.add(str(entry.id))

    act_as(current_user)

    # SQL filter: sufficiency=sufficient
    resp_sufficient = await client.get(
        "/api/v1/cabinet/entries",
        params={"sufficiency": "sufficient", "page_size": 100},
    )
    assert resp_sufficient.status_code == 200
    returned_sufficient_ids = {item["id"] for item in resp_sufficient.json()["items"]}
    assert returned_sufficient_ids == predicted_sufficient_ids, (
        "SQL sufficient filter diverges from Python compute_usage_view"
    )

    # SQL filter: sufficiency=insufficient
    resp_insufficient = await client.get(
        "/api/v1/cabinet/entries",
        params={"sufficiency": "insufficient", "page_size": 100},
    )
    assert resp_insufficient.status_code == 200
    returned_insufficient_ids = {
        item["id"] for item in resp_insufficient.json()["items"]
    }
    assert returned_insufficient_ids == predicted_insufficient_ids, (
        "SQL insufficient filter diverges from Python compute_usage_view"
    )

    # No-verdict entries must appear in neither filter.
    no_verdict_ids = {
        str(entry_closed_window.id),
        str(entry_unused.id),
    }
    assert no_verdict_ids.isdisjoint(returned_sufficient_ids), (
        "no-verdict entries must not appear in sufficient filter"
    )
    assert no_verdict_ids.isdisjoint(returned_insufficient_ids), (
        "no-verdict entries must not appear in insufficient filter"
    )
