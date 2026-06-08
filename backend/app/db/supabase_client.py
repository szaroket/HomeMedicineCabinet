"""Configured supabase-py client instance for use across the application."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from supabase import Client

_client: "Client | None" = None


def get_supabase() -> "Client":
    """Return the module-level Supabase client, initialising it on first call."""
    global _client
    if _client is None:
        from supabase import create_client

        from app.core.config import settings

        _client = create_client(settings.supabase_url, settings.supabase_anon_key)
    return _client
