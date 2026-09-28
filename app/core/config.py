from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Neuro Coins"
    app_env: str = "local"
    database_url: str = "sqlite+pysqlite:///./data/neurocoin.db"
    secret_key: str = "change-this-local-secret"
    session_cookie: str = "session"
    csrf_cookie: str = "csrf_token"
    session_max_age: int = 60 * 60 * 24 * 14

    model_config = SettingsConfigDict(extra="ignore")


@lru_cache
def get_settings() -> Settings:
    return Settings()
