"""Pydantic response schemas for the medicines endpoints."""

from pydantic import BaseModel


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

    name: str
    strength: str | None
    pharmaceutical_form: str | None
    active_ingredient: str | None
