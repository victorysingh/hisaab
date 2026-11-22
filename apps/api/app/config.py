"""Application settings loaded from environment variables and .env."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration for the API."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    demo_mode: bool = False
    demo_owner_user_id: str = ""
    demo_today: str = ""
    supabase_url: str = ""
    supabase_service_key: str = ""
    web_origin: str = ""


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return the cached Settings instance."""
    return Settings()
