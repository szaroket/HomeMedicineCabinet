"""Users API schemas."""

from pydantic import BaseModel


class UserPreferencesOut(BaseModel):
    """Response schema for user preferences."""

    expiry_threshold_days: int
    close_to_finish_threshold_days: int
    min_package_count: int
