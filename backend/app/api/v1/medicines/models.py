import uuid
from decimal import Decimal

import sqlalchemy as sa
from sqlmodel import Field, SQLModel


class MedicationRegistry(SQLModel, table=True):
    __tablename__ = "medication_registry"  # pyright: ignore[reportAssignmentType]

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    source_product_id: str | None = Field(default=None, sa_type=sa.Text)
    gtin: str | None = Field(default=None, sa_type=sa.Text)
    name: str = Field(index=True, sa_type=sa.Text)
    active_ingredient: str | None = Field(default=None, sa_type=sa.Text)
    strength: str | None = Field(default=None, sa_type=sa.Text)
    pharmaceutical_form: str | None = Field(default=None, sa_type=sa.Text)
    marketing_authorization_holder: str | None = Field(default=None, sa_type=sa.Text)
    manufacturer: str | None = Field(default=None, sa_type=sa.Text)
    route_of_administration: str | None = Field(default=None, sa_type=sa.Text)
    atc_code: str | None = Field(default=None, sa_type=sa.Text)
    availability_category: str | None = Field(default=None, sa_type=sa.Text)
    capacity: Decimal | None = Field(default=None, sa_type=sa.Numeric)
    capacity_unit: str | None = Field(default=None, sa_type=sa.Text)
    is_tablet_based: bool = Field(default=False)
    leaflet_url: str | None = Field(default=None, sa_type=sa.Text)
    specification_url: str | None = Field(default=None, sa_type=sa.Text)
