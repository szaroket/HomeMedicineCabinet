import uuid

import sqlalchemy as sa
from sqlmodel import Field, SQLModel


class MedicationRegistry(SQLModel, table=True):
    __tablename__ = "medication_registry"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    name: str = Field(index=True, sa_type=sa.Text())
    active_ingredient: str | None = Field(default=None, sa_type=sa.Text())
    tablet_count: int | None = None
    producer: str | None = Field(default=None, sa_type=sa.Text())
    route_of_administration: str | None = Field(default=None, sa_type=sa.Text())
    leaflet_url: str | None = Field(default=None, sa_type=sa.Text())
    specification_url: str | None = Field(default=None, sa_type=sa.Text())
