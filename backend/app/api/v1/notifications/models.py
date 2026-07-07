import uuid
from datetime import datetime, timezone

import sqlalchemy as sa
from sqlmodel import Field, SQLModel


class DismissedNotification(SQLModel, table=True):
    __tablename__ = "dismissed_notifications"  # pyright: ignore[reportAssignmentType]
    __table_args__ = (
        sa.UniqueConstraint(
            "user_id",
            "cabinet_entry_id",
            "trigger_type",
            name="uq_dismissed_user_entry_trigger",
        ),
    )

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    user_id: uuid.UUID = Field(foreign_key="users.id")
    cabinet_entry_id: uuid.UUID = Field(
        sa_column=sa.Column(
            sa.Uuid(),
            sa.ForeignKey("cabinet_entries.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        )
    )
    trigger_type: str = Field(sa_type=sa.Text)
    dismissed_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_type=sa.DateTime(timezone=True),  # pyright: ignore[reportArgumentType]
    )
