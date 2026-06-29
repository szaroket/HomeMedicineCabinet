"""Cabinet request and response schemas."""

import uuid
from datetime import date
from decimal import Decimal
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.utilities.types import DosagePeriod, NonEmptyStr


class UsageFields(BaseModel):
    """Usage/dosage fields shared by the POST and PATCH write paths."""

    is_used: bool = False
    dosage_times: int | None = Field(default=None, ge=1, le=24)
    dosage_period: DosagePeriod | None = None
    dosage_amount: int | None = Field(default=None, ge=1, le=100)
    dosage_start_date: date | None = None
    dosage_end_date: date | None = None


class CabinetCategory(StrEnum):
    """Cabinet entry category filter values."""

    important = "important"
    used = "used"


class CabinetStatus(StrEnum):
    """Cabinet entry expiry status filter values."""

    valid = "valid"
    expiring = "expiring"
    expired = "expired"


class CabinetOrder(StrEnum):
    """Sort direction for cabinet entry list."""

    asc = "asc"
    desc = "desc"


class SufficiencyFilter(StrEnum):
    """Sufficiency filter values for cabinet entry list."""

    insufficient = "insufficient"
    sufficient = "sufficient"


class CabinetListParams(BaseModel):
    """Query parameters for GET /cabinet/entries."""

    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    status: CabinetStatus | None = None
    category: CabinetCategory | None = None
    below_minimum: bool | None = None
    sufficiency: SufficiencyFilter | None = None
    search: NonEmptyStr | None = None
    order: CabinetOrder = CabinetOrder.asc
    page: int = Field(1, ge=1)
    page_size: Literal[20, 50, 100] = 20

    @field_validator("page_size", mode="before")
    @classmethod
    def coerce_page_size(cls, v: object) -> object:
        """Coerce string query param to int before Literal validation.

        Args:
            v: The raw incoming value.

        Returns:
            Integer value when input is a numeric string, original value otherwise.
        """
        if isinstance(v, str):
            try:
                return int(v)
            except ValueError:
                pass
        return v


class AddEntryRequest(BaseModel):
    """Validated request body for POST /cabinet/entries."""

    medication_registry_id: uuid.UUID
    package_count: int
    expiry_date: date
    partial_tablet_count: int | None = None
    is_important: bool = False
    usage: UsageFields | None = None

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
    is_important: bool
    is_used: bool = False
    dosage_times: int | None = None
    dosage_period: DosagePeriod | None = None
    dosage_amount: int | None = None
    dosage_start_date: date | None = None
    dosage_end_date: date | None = None


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
    is_important: bool
    below_minimum: bool
    active_ingredient: str | None
    route_of_administration: str | None
    leaflet_url: str | None
    specification_url: str | None
    is_used: bool = False
    dosage_times: int | None = None
    dosage_period: DosagePeriod | None = None
    dosage_amount: int | None = None
    dosage_start_date: date | None = None
    dosage_end_date: date | None = None
    days_of_supply: int | None = None
    days_until_end: int | None = None
    is_sufficient: bool | None = None


class SetImportantRequest(BaseModel):
    """Request body for PATCH /cabinet/entries/{entry_id}."""

    is_important: bool


class CabinetPageOut(BaseModel):
    """Paginated response envelope for GET /cabinet/entries."""

    items: list[CabinetEntryOut]
    total: int
    page: int
    page_size: int


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
