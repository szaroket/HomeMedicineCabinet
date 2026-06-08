"""Configured supabase-py client instance for use across the application."""

from supabase import Client, create_client

from app.core.config import settings

supabase: Client = create_client(settings.supabase_url, settings.supabase_anon_key)
