import uuid
from datetime import date, datetime, timezone

import sqlalchemy as sa
from sqlmodel import Field, SQLModel


class CabinetEntry(SQLModel, table=True):
    __tablename__ = "cabinet_entries"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    user_id: uuid.UUID = Field(foreign_key="users.id")
    medication_registry_id: uuid.UUID = Field(foreign_key="medication_registry.id")
    package_count: int
    partial_tablet_count: int | None = None
    expiry_date: date
    is_important: bool = Field(default=False)
    is_used: bool = Field(default=False)
    dosage_times: int | None = None
    dosage_period: str | None = Field(default=None, sa_type=sa.Text())
    dosage_amount: int | None = None
    dosage_start_date: date | None = None
    dosage_end_date: date | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
