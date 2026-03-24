from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_env: str = "development"
    database_url: str = "postgresql+psycopg://eve_trader:eve_trader@localhost:5432/eve_trader"
    redis_url: str = "redis://localhost:6379/0"
    frontend_url: str = "http://localhost:5173"
    esi_client_id: str = "change-me"
    esi_client_secret: str = "change-me"
    esi_callback_url: str = "http://localhost:8000/api/auth/callback"
    esi_compatibility_date: str = "2026-02-24"
    a4e_user_agent: str = "eve-station-trader/0.1.0 (contact: change-me)"
    ccp_static_data_jsonl_url: str = "https://developers.eveonline.com/static-data/eve-online-static-data-latest-jsonl.zip"
    poll_interval_seconds: int = 60

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")


@lru_cache
def get_settings() -> Settings:
    return Settings()
