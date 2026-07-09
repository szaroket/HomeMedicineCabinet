"""Notifications request and response schemas."""

import uuid
from enum import StrEnum

from pydantic import BaseModel


class TriggerType(StrEnum):
    """Closed set of notification trigger types."""

    EXPIRY = "expiry"
    BELOW_MINIMUM = "below_minimum"
    RUN_OUT = "run_out"


class NotificationOut(BaseModel):
    """Response schema for a single active notification."""

    trigger_type: TriggerType
    cabinet_entry_id: uuid.UUID
    medication_name: str
    days_remaining: int | None


class NotificationListOut(BaseModel):
    """Response envelope for GET /notifications."""

    items: list[NotificationOut]


class DismissRequest(BaseModel):
    """Request body for POST /notifications/dismiss."""

    cabinet_entry_id: uuid.UUID
    trigger_type: TriggerType
