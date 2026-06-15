"""Cabinet request and response schemas."""

import uuid
from datetime import date
from decimal import Decimal

from pydantic import BaseModel, field_validator


class AddEntryRequest(BaseModel):
    """Validated request body for POST /cabinet/entries."""

    medication_registry_id: uuid.UUID
    package_count: int
    expiry_date: date
    partial_tablet_count: int | None = None

    @field_validator("package_count")
    @classmethod
    def package_count_at_least_one(cls, v: int) -> int:
        """Validate package_count >= 1.

        Args:
            v: The incoming value.

        Returns:
            The value unchanged if valid.

        Raises:
            ValueError: When the count is less than 1.
        """
        if v < 1:
            raise ValueError("package_count must be at least 1")
        return v

    @field_validator("partial_tablet_count")
    @classmethod
    def partial_tablet_count_at_least_one(cls, v: int | None) -> int | None:
        """Validate partial_tablet_count >= 1 when provided.

        Args:
            v: The incoming value or None.

        Returns:
            The value unchanged if valid.

        Raises:
            ValueError: When the count is less than 1.
        """
        if v is not None and v < 1:
            raise ValueError("partial_tablet_count must be at least 1 when provided")
        return v


class AddEntryOut(BaseModel):
    """Response schema for a single entry as returned by POST /cabinet/entries.

    Status is omitted — callers should fetch GET /cabinet/entries for up-to-date
    status computed against the current date and user threshold.
    """

    id: uuid.UUID
    name: str
    strength: str | None
    pharmaceutical_form: str | None
    capacity: Decimal | None
    capacity_unit: str | None
    is_tablet_based: bool
    package_count: int
    partial_tablet_count: int | None
    expiry_date: date
    total_tablets: int | None


class CabinetEntryOut(BaseModel):
    """Response schema for a single cabinet entry, including computed status."""

    id: uuid.UUID
    name: str
    strength: str | None
    pharmaceutical_form: str | None
    capacity: Decimal | None
    capacity_unit: str | None
    is_tablet_based: bool
    package_count: int
    partial_tablet_count: int | None
    expiry_date: date
    total_tablets: int | None
    status: str
    route_of_administration: str | None
    leaflet_url: str | None
    specification_url: str | None


class MergeSummary(BaseModel):
    """Before/after totals returned when an add operation merges with an existing entry."""

    previous_package_count: int
    previous_partial_tablet_count: int | None
    previous_total_tablets: int | None
    added_total_tablets: int | None
    new_total_tablets: int | None


class AddEntryResult(BaseModel):
    """Envelope returned by POST /cabinet/entries."""

    merged: bool
    entry: AddEntryOut
    merge_summary: MergeSummary | None
