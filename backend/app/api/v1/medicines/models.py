import uuid

from sqlmodel import Field, SQLModel


class MedicationRegistry(SQLModel, table=True):
    __tablename__ = "medication_registry"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    name: str = Field(index=True)
    active_ingredient: str | None = None
    tablet_count: int | None = None
    producer: str | None = None
    route_of_administration: str | None = None
    leaflet_url: str | None = None
    specification_url: str | None = None
