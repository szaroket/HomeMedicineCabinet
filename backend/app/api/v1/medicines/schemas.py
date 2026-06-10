"""Pydantic response schemas for the medicines endpoints."""

import uuid
from decimal import Decimal

from pydantic import BaseModel, ConfigDict


class ProductOut(BaseModel):
    """A distinct product result from the registry search.

    A product groups all pack-size variants that share the same name,
    strength, and pharmaceutical form. The add flow uses it to drive the
    second (pack-size) step of the picker.

    Attributes:
        name: Product name.
        strength: Dosage strength, or None when not recorded.
        pharmaceutical_form: Form (tablet, syrup, ...), or None when not recorded.
        active_ingredient: Active ingredient, or None when not recorded.
    """

    model_config = ConfigDict(from_attributes=True, extra="ignore")

    name: str
    strength: str | None
    pharmaceutical_form: str | None
    active_ingredient: str | None


class VariantOut(BaseModel):
    """A concrete pack-size variant from the registry.

    Returned by the variants endpoint so the add flow can reference a specific
    registry row by ``id`` and display its capacity/unit to the user.

    Attributes:
        id: Registry row UUID (used as ``medication_registry_id`` in the add request).
        name: Product name.
        strength: Dosage strength, or None when not recorded.
        pharmaceutical_form: Form (tablet, syrup, ...), or None when not recorded.
        capacity: Pack size (tablets per package for tablet-based products), or None.
        capacity_unit: Unit label for the capacity value, or None.
        is_tablet_based: True when the product is counted in tablets.
        active_ingredient: Active ingredient, or None when not recorded.
        route_of_administration: Administration route, or None when not recorded.
    """

    model_config = ConfigDict(from_attributes=True, extra="ignore")

    id: uuid.UUID
    name: str
    strength: str | None
    pharmaceutical_form: str | None
    capacity: Decimal | None
    capacity_unit: str | None
    is_tablet_based: bool
    active_ingredient: str | None
    route_of_administration: str | None
