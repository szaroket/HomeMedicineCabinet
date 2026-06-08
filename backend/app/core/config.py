"""Application configuration loaded from environment variables."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Pydantic-settings singleton for all environment-backed configuration.

    Attributes:
        database_url: Async Postgres connection string (asyncpg).
        supabase_url: Base URL of the Supabase project (e.g. https://xxx.supabase.co).
        supabase_anon_key: Supabase anon/public API key.
        jwt_audience: Expected `aud` claim in Supabase JWTs.
        jwt_algorithms: Allowed signing algorithms for JWT verification.
    """

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str
    supabase_url: str
    supabase_anon_key: str

    jwt_audience: str = "authenticated"
    jwt_algorithms: list[str] = ["ES256", "RS256"]

    @property
    def jwt_issuer(self) -> str:
        """Return the JWT issuer URL derived from the Supabase project URL."""
        return f"{self.supabase_url}/auth/v1"

    @property
    def jwks_url(self) -> str:
        """Return the JWKS endpoint URL used to fetch public signing keys."""
        return f"{self.jwt_issuer}/.well-known/jwks.json"


settings = Settings()
