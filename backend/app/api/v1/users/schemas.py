"""Users API schemas."""

from pydantic import BaseModel, Field


class UserPreferencesOut(BaseModel):
    """Response schema for user preferences."""

    expiry_threshold_days: int
    close_to_finish_threshold_days: int
    min_package_count: int


class UpdatePreferencesRequest(BaseModel):
    """Request schema for updating user preferences."""

    expiry_threshold_days: int = Field(ge=7, le=90)
    close_to_finish_threshold_days: int = Field(ge=1)
    min_package_count: int = Field(ge=1, le=10)
