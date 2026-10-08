from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "ktru-classifier"
    app_version: str = "0.1.0"

    database_url: str = "postgresql+psycopg://app:app@localhost:5432/ktru"
    redis_url: str = "redis://localhost:6379/0"

    uploads_dir: str = "uploads"
    max_upload_mb: int = 10
    max_items: int = 1000

    default_page_size: int = 50
    max_page_size: int = 200


@lru_cache
def get_settings() -> Settings:
    return Settings()
