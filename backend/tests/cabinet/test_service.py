"""Unit tests for cabinet domain logic (no DB, no I/O)."""

from datetime import date, timedelta

import pytest

from app.api.v1.cabinet.service import (
    Status,
    TabletPool,
    classify_status,
    merge_non_tablet_entry,
    merge_tablet_entry,
    normalize_tablet_pool,
    total_tablets,
)

# ---------------------------------------------------------------------------
# total_tablets
# ---------------------------------------------------------------------------


class TestTotalTablets:
    @pytest.mark.parametrize(
        ("package_count", "partial_tablet_count", "tablets_per_package", "expected"),
        [
            (3, None, 20, 60),
            (1, None, 20, 20),
            (2, 5, 20, 25),  # 1 full + 5 tablets in second package → 25
            (1, 10, 20, 10),  # single package, partially used
            (3, 7, 20, 47),  # 2*20 + 7
        ],
    )
    def test_total_tablets(
        self, package_count, partial_tablet_count, tablets_per_package, expected
    ):
        assert (
            total_tablets(
                package_count=package_count,
                partial_tablet_count=partial_tablet_count,
                tablets_per_package=tablets_per_package,
            )
            == expected
        )


# ---------------------------------------------------------------------------
# normalize_tablet_pool
# ---------------------------------------------------------------------------


class TestNormalizeTabletPool:
    @pytest.mark.parametrize(
        ("total", "tablets_per_package", "expected"),
        [
            (40, 20, TabletPool(2, None)),  # even divide clears partial
            (25, 20, TabletPool(2, 5)),  # remainder produces partial
            (5, 20, TabletPool(1, 5)),  # less than one package
            (20, 20, TabletPool(1, None)),  # exactly one package
            (200, 20, TabletPool(10, None)),  # large even
            (201, 20, TabletPool(11, 1)),  # large with remainder
        ],
    )
    def test_normalize_tablet_pool(self, total, tablets_per_package, expected):
        assert (
            normalize_tablet_pool(
                total=total,
                tablets_per_package=tablets_per_package,
            )
            == expected
        )


# ---------------------------------------------------------------------------
# merge_tablet_entry
# ---------------------------------------------------------------------------


class TestMergeTabletEntry:
    @pytest.mark.parametrize(
        (
            "existing_package_count",
            "existing_partial_tablet_count",
            "new_package_count",
            "new_partial_tablet_count",
            "tablets_per_package",
            "expected",
        ),
        [
            # two full packages → even result
            (1, None, 1, None, 20, TabletPool(2, None)),
            # partial on new side only: 20+5=25 → 2 pkg partial 5
            (1, None, 1, 5, 20, TabletPool(2, 5)),
            # partial on existing side only: 5+20=25 → 2 pkg partial 5
            (1, 5, 1, None, 20, TabletPool(2, 5)),
            # partial on both, even result: 10+10=20 → 1 full pkg
            (1, 10, 1, 10, 20, TabletPool(1, None)),
            # partial on both, remainder: 15+15=30 → 2 pkg partial 10
            (1, 15, 1, 15, 20, TabletPool(2, 10)),
            # multi-package: 60+27=87 → 5 pkg partial 7
            (3, None, 2, 7, 20, TabletPool(5, 7)),
            # worked example from plan: 20+5=25 → 2 pkg partial 5
            (1, None, 1, 5, 20, TabletPool(2, 5)),
        ],
    )
    def test_merge_tablet_entry(
        self,
        existing_package_count,
        existing_partial_tablet_count,
        new_package_count,
        new_partial_tablet_count,
        tablets_per_package,
        expected,
    ):
        assert (
            merge_tablet_entry(
                existing_package_count=existing_package_count,
                existing_partial_tablet_count=existing_partial_tablet_count,
                new_package_count=new_package_count,
                new_partial_tablet_count=new_partial_tablet_count,
                tablets_per_package=tablets_per_package,
            )
            == expected
        )


# ---------------------------------------------------------------------------
# merge_non_tablet_entry
# ---------------------------------------------------------------------------


class TestMergeNonTabletEntry:
    @pytest.mark.parametrize(
        ("existing_packages", "new_packages", "expected"),
        [
            (3, 2, 5),
            (1, 1, 2),
            (100, 50, 150),
        ],
    )
    def test_merge_non_tablet_entry(self, existing_packages, new_packages, expected):
        assert (
            merge_non_tablet_entry(
                existing_packages=existing_packages,
                new_packages=new_packages,
            )
            == expected
        )


# ---------------------------------------------------------------------------
# classify_status
# ---------------------------------------------------------------------------


class TestClassifyStatus:
    TODAY = date(2026, 6, 9)
    THRESHOLD = 30

    @pytest.mark.parametrize(
        ("expiry_date", "today", "expiry_threshold_days", "expected"),
        [
            # expired
            (TODAY - timedelta(days=1), TODAY, THRESHOLD, Status.EXPIRED),
            # expiring: today
            (TODAY, TODAY, THRESHOLD, Status.EXPIRING),
            # expiring: exactly at threshold edge
            (TODAY + timedelta(days=THRESHOLD), TODAY, THRESHOLD, Status.EXPIRING),
            # expiring: one day before expiry
            (TODAY + timedelta(days=1), TODAY, THRESHOLD, Status.EXPIRING),
            # valid: one day past threshold
            (TODAY + timedelta(days=THRESHOLD + 1), TODAY, THRESHOLD, Status.VALID),
            # valid: far future
            (TODAY + timedelta(days=365), TODAY, THRESHOLD, Status.VALID),
            # zero threshold: today is expiring
            (TODAY, TODAY, 0, Status.EXPIRING),
            # zero threshold: tomorrow is valid
            (TODAY + timedelta(days=1), TODAY, 0, Status.VALID),
        ],
    )
    def test_classify_status(self, expiry_date, today, expiry_threshold_days, expected):
        assert (
            classify_status(
                expiry_date=expiry_date,
                today=today,
                expiry_threshold_days=expiry_threshold_days,
            )
            == expected
        )
