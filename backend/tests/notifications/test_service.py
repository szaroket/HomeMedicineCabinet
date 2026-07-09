"""Unit tests for notifications service: pure trigger predicates and ordering."""

from datetime import date
from uuid import uuid4

import pytest

from app.api.v1.cabinet.schemas import CabinetEntryOut
from app.api.v1.notifications.schemas import NotificationOut, TriggerType
from app.api.v1.notifications.service import (
    is_below_minimum_active,
    is_expiry_active,
    is_run_out_active,
    order_notifications,
)


def _entry(**overrides: object) -> CabinetEntryOut:
    """Build a CabinetEntryOut with sensible defaults, overridable per test."""
    defaults: dict[str, object] = {
        "id": uuid4(),
        "name": "Apap 500mg tabl.",
        "strength": "500mg",
        "pharmaceutical_form": "tabl.",
        "capacity": None,
        "capacity_unit": "tabl.",
        "is_tablet_based": True,
        "package_count": 2,
        "partial_tablet_count": None,
        "expiry_date": date(2030, 1, 1),
        "total_tablets": 40,
        "status": "valid",
        "is_important": False,
        "below_minimum": False,
        "active_ingredient": "paracetamol",
        "route_of_administration": None,
        "leaflet_url": None,
        "specification_url": None,
        "is_used": False,
        "dosage_times": None,
        "dosage_period": None,
        "dosage_amount": None,
        "dosage_start_date": None,
        "dosage_end_date": None,
        "days_of_supply": None,
        "days_until_end": None,
        "is_sufficient": None,
    }
    defaults.update(overrides)
    return CabinetEntryOut(**defaults)


# ---------------------------------------------------------------------------
# is_expiry_active
# ---------------------------------------------------------------------------


class TestIsExpiryActive:
    @pytest.mark.parametrize(
        ("status", "expected"),
        [
            ("valid", False),
            ("expiring", True),
            ("expired", True),
        ],
    )
    def test_is_expiry_active(self, status, expected):
        assert is_expiry_active(_entry(status=status)) is expected


# ---------------------------------------------------------------------------
# is_below_minimum_active
# ---------------------------------------------------------------------------


class TestIsBelowMinimumActive:
    @pytest.mark.parametrize("below_minimum", [True, False])
    def test_is_below_minimum_active(self, below_minimum):
        assert (
            is_below_minimum_active(_entry(below_minimum=below_minimum))
            == below_minimum
        )


# ---------------------------------------------------------------------------
# is_run_out_active
# ---------------------------------------------------------------------------


class TestIsRunOutActive:
    def test_active_when_insufficient_within_threshold(self):
        entry = _entry(
            is_used=True,
            is_tablet_based=True,
            dosage_end_date=date(2030, 6, 1),
            is_sufficient=False,
            days_of_supply=5,
        )
        assert is_run_out_active(entry, close_to_finish_threshold_days=7) is True

    def test_inactive_when_days_of_supply_above_threshold(self):
        entry = _entry(
            is_used=True,
            is_tablet_based=True,
            dosage_end_date=date(2030, 6, 1),
            is_sufficient=False,
            days_of_supply=8,
        )
        assert is_run_out_active(entry, close_to_finish_threshold_days=7) is False

    def test_inactive_when_sufficient(self):
        entry = _entry(
            is_used=True,
            is_tablet_based=True,
            dosage_end_date=date(2030, 6, 1),
            is_sufficient=True,
            days_of_supply=5,
        )
        assert is_run_out_active(entry, close_to_finish_threshold_days=7) is False

    def test_inactive_when_not_used(self):
        entry = _entry(
            is_used=False,
            is_tablet_based=True,
            dosage_end_date=date(2030, 6, 1),
            is_sufficient=False,
            days_of_supply=5,
        )
        assert is_run_out_active(entry, close_to_finish_threshold_days=7) is False

    def test_inactive_when_not_tablet_based(self):
        entry = _entry(
            is_used=True,
            is_tablet_based=False,
            dosage_end_date=date(2030, 6, 1),
            is_sufficient=False,
            days_of_supply=5,
        )
        assert is_run_out_active(entry, close_to_finish_threshold_days=7) is False

    def test_inactive_when_no_end_date(self):
        entry = _entry(
            is_used=True,
            is_tablet_based=True,
            dosage_end_date=None,
            is_sufficient=None,
            days_of_supply=5,
        )
        assert is_run_out_active(entry, close_to_finish_threshold_days=7) is False


# ---------------------------------------------------------------------------
# order_notifications
# ---------------------------------------------------------------------------


class TestOrderNotifications:
    def test_urgency_ordering_across_mixed_types(self):
        entry_expired = uuid4()
        entry_below_min = uuid4()
        entry_expiring_soon = uuid4()
        entry_expiring_later = uuid4()
        entry_run_out = uuid4()

        items = [
            NotificationOut(
                trigger_type=TriggerType.RUN_OUT,
                cabinet_entry_id=entry_run_out,
                medication_name="C",
                days_remaining=5,
            ),
            NotificationOut(
                trigger_type=TriggerType.EXPIRY,
                cabinet_entry_id=entry_expiring_later,
                medication_name="D",
                days_remaining=10,
            ),
            NotificationOut(
                trigger_type=TriggerType.BELOW_MINIMUM,
                cabinet_entry_id=entry_below_min,
                medication_name="B",
                days_remaining=None,
            ),
            NotificationOut(
                trigger_type=TriggerType.EXPIRY,
                cabinet_entry_id=entry_expired,
                medication_name="A",
                days_remaining=-2,
            ),
            NotificationOut(
                trigger_type=TriggerType.EXPIRY,
                cabinet_entry_id=entry_expiring_soon,
                medication_name="E",
                days_remaining=5,
            ),
        ]

        ordered = order_notifications(items)
        ordered_ids = [item.cabinet_entry_id for item in ordered]

        assert ordered_ids == [
            entry_expired,  # already expired sorts first
            entry_below_min,  # None -> 0 days, ahead of positive-day items
            entry_expiring_soon,  # 5 days, expiry beats run_out on same day
            entry_run_out,  # 5 days, run_out after expiry
            entry_expiring_later,  # 10 days, latest
        ]

    @pytest.mark.parametrize("days_remaining", [-1, 0])
    def test_expired_bucket_boundary_does_not_crash_on_single_item(
        self, days_remaining
    ):
        item = NotificationOut(
            trigger_type=TriggerType.EXPIRY,
            cabinet_entry_id=uuid4(),
            medication_name="X",
            days_remaining=days_remaining,
        )
        assert order_notifications([item]) == [item]

    def test_expiry_ahead_of_run_out_at_boundary_zero_days(self):
        entry_expiry = uuid4()
        entry_run_out = uuid4()
        items = [
            NotificationOut(
                trigger_type=TriggerType.RUN_OUT,
                cabinet_entry_id=entry_run_out,
                medication_name="Y",
                days_remaining=0,
            ),
            NotificationOut(
                trigger_type=TriggerType.EXPIRY,
                cabinet_entry_id=entry_expiry,
                medication_name="Z",
                days_remaining=0,
            ),
        ]
        ordered = order_notifications(items)
        assert [item.cabinet_entry_id for item in ordered] == [
            entry_expiry,
            entry_run_out,
        ]
