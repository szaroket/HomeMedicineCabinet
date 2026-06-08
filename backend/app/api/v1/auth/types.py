"""Internal data structures for the auth domain."""

from typing import NamedTuple
from uuid import UUID


class CurrentUser(NamedTuple):
    """Authenticated user identity extracted from a verified JWT.

    Attributes:
        id: The user's UUID, equal to the Supabase auth `sub` claim.
        email: The user's email address.
    """

    id: UUID
    email: str
